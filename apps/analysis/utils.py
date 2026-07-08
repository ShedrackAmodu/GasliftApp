import statistics
import logging
from .models import WellTrendAnalysis, AnalysisWeights

logger = logging.getLogger(__name__)

# Map magnitude descriptors to numeric factors for scoring
MAGNITUDE_FACTOR = {
    'slightly': 1,
    'moderately': 2,
    'aggressively': 3,
}


def _kendall_tau(x, y):
    """
    Pure-Python implementation of Kendall's tau-b rank correlation.
    Returns (tau, p_value) approximating scipy.stats.kendalltau.
    """
    n = len(x)
    if n < 2:
        return 0, 1.0

    # Rank both arrays
    x_ranked = sorted(range(n), key=lambda i: x[i])
    y_ranked = sorted(range(n), key=lambda i: y[i])

    concordant = 0
    discordant = 0
    ties_x = 0
    ties_y = 0

    for i in range(n - 1):
        for j in range(i + 1, n):
            x_diff = x[j] - x[i]
            y_diff = y[j] - y[i]

            if x_diff == 0 and y_diff == 0:
                continue
            elif x_diff == 0:
                ties_x += 1
            elif y_diff == 0:
                ties_y += 1
            elif (x_diff > 0 and y_diff > 0) or (x_diff < 0 and y_diff < 0):
                concordant += 1
            else:
                discordant += 1

    n_pairs = n * (n - 1) / 2
    denominator = ((n_pairs - ties_x) * (n_pairs - ties_y)) ** 0.5

    if denominator == 0:
        return 0, 1.0

    tau = (concordant - discordant) / denominator

    # Approximate p-value using normal approximation
    # Under independence, tau ~ N(0, 2*(2n+5)/(9*n*(n-1)))
    variance = (2 * (2 * n + 5)) / (9 * n * (n - 1))
    if variance <= 0:
        return tau, 1.0

    z = tau / (variance ** 0.5)

    # Standard normal CDF approximation (Abramowitz & Stegun)
    p_value = _normal_cdf(-abs(z)) * 2  # two-tailed

    return tau, p_value


def _normal_cdf(x):
    """Approximate standard normal CDF using the Hastings approximation."""
    if x < 0:
        return 1 - _normal_cdf(-x)

    # Constants for Abramowitz and Stegun approximation
    b0 = 0.2316419
    b1 = 0.319381530
    b2 = -0.356563782
    b3 = 1.781477937
    b4 = -1.821255978
    b5 = 1.330274429

    t = 1.0 / (1.0 + b0 * x)
    phi = (1.0 / (2.5066282746310002)) * (2.718281828459045 ** (-x * x / 2.0))

    return 1.0 - phi * (b1 * t + b2 * t ** 2 + b3 * t ** 3 + b4 * t ** 4 + b5 * t ** 5)


class TrendAnalyzer:
    """Analyzes well trends using Mann-Kendall and Sen's slope"""

    @staticmethod
    def _extract_series(data_rows, field):
        """
        Extract a numeric list from a list of dict rows for a given field.
        Skips None/empty values.
        """
        series = []
        for row in data_rows:
            val = row.get(field)
            if val is not None and val != '':
                try:
                    series.append(float(val))
                except (ValueError, TypeError):
                    series.append(None)
            else:
                series.append(None)
        return series

    @staticmethod
    def mann_kendall_test(data_series):
        """
        Perform Mann-Kendall trend test on a plain list of numbers.
        Returns: trend direction (increasing, decreasing, no_trend), tau
        """
        # Remove None/NaN values and track indices
        clean_values = [v for v in data_series if v is not None]
        if len(clean_values) < 3:
            return 'no_trend', 0

        # Use indices as the x-axis (time steps)
        indices = list(range(len(clean_values)))

        tau, p_value = _kendall_tau(indices, clean_values)

        # Significance level
        if p_value > 0.05:
            return 'no_trend', tau

        if tau > 0:
            return 'increasing', tau
        else:
            return 'decreasing', tau

    @staticmethod
    def sen_slope(data_series):
        """
        Calculate Sen's slope estimator on a plain list of numbers.
        Returns: slope value (rate of change)
        """
        clean_values = [v for v in data_series if v is not None]
        if len(clean_values) < 3:
            return 0

        n = len(clean_values)
        slopes = []

        for i in range(n - 1):
            for j in range(i + 1, n):
                slope = (clean_values[j] - clean_values[i]) / (j - i)
                slopes.append(slope)

        if slopes:
            return statistics.median(slopes)
        return 0

    @staticmethod
    def classify_magnitude(slope, data_series):
        """Classify magnitude of trend as Slightly, Moderately, or Aggressively"""
        if slope == 0:
            return None

        # Calculate relative change over range
        clean_values = [v for v in data_series if v is not None]
        if len(clean_values) < 2:
            return 'slightly'

        data_range = max(clean_values) - min(clean_values)
        if data_range == 0:
            return 'slightly'

        relative_change = abs(slope) / data_range

        if relative_change < 0.05:
            return 'slightly'
        elif relative_change < 0.15:
            return 'moderately'
        else:
            return 'aggressively'

    @staticmethod
    def analyze_well(well_data, weights):
        """
        Analyze a single well's trends using the full scoring methodology.
        `well_data` is a list of dicts (rows), sorted by date.

        Returns: trend analysis dict
        """
        analysis = {
            'bsw_trend': None,
            'bsw_slope': 0,
            'bsw_magnitude': None,
            'oil_rate_trend': None,
            'oil_rate_slope': 0,
            'oil_rate_magnitude': None,
            'glr_trend': None,
            'glr_slope': 0,
            'glr_magnitude': None,
            'tubing_pressure_trend': None,
            'tubing_pressure_slope': 0,
            'tubing_pressure_magnitude': None,
            'candidate_score': 0,
            'bsw_flag': False,
            'oil_rate_flag': False,
            'glr_flag': False,
            # Additional well metadata
            'prod_method': '',
            'test_status': '',
            'flow_line_pressure': 0,
            'well_choke_size': '',
        }

        # Extract last valid metadata values from the well data
        for row in reversed(well_data):
            if not analysis['prod_method'] and row.get('Prod Method'):
                analysis['prod_method'] = str(row['Prod Method'])
            if not analysis['test_status'] and row.get('Test Status'):
                analysis['test_status'] = str(row['Test Status'])
            if not analysis['flow_line_pressure'] and row.get('Flow Line Pressure (psi)'):
                try:
                    analysis['flow_line_pressure'] = float(row['Flow Line Pressure (psi)'])
                except (ValueError, TypeError):
                    pass
            if not analysis['well_choke_size'] and row.get('Well Choke Size'):
                analysis['well_choke_size'] = str(row['Well Choke Size'])

        # Helper to extract numeric series
        def get_series(field):
            return [r.get(field) for r in well_data]

        score = 0

        # Analyze BSW (should be INCREASING = bad)
        bsw_series = get_series('BS&W (%)')
        bsw_series_clean = [v for v in bsw_series if v is not None]
        if len(bsw_series_clean) >= 3:
            bsw_trend, tau = TrendAnalyzer.mann_kendall_test(bsw_series)
            bsw_slope = TrendAnalyzer.sen_slope(bsw_series)
            analysis['bsw_trend'] = bsw_trend
            analysis['bsw_slope'] = float(bsw_slope)
            analysis['bsw_magnitude'] = TrendAnalyzer.classify_magnitude(bsw_slope, bsw_series)
            analysis['bsw_flag'] = bsw_trend == 'increasing'

            if analysis['bsw_flag'] and analysis['bsw_magnitude']:
                magnitude_factor = MAGNITUDE_FACTOR.get(analysis['bsw_magnitude'], 1)
                score += 1 * magnitude_factor * weights.bsw_weight

        # Analyze Oil Rate (should be DECREASING = bad)
        oil_series = get_series('Net Oil (bopd)')
        oil_series_clean = [v for v in oil_series if v is not None]
        if len(oil_series_clean) >= 3:
            oil_trend, tau = TrendAnalyzer.mann_kendall_test(oil_series)
            oil_slope = TrendAnalyzer.sen_slope(oil_series)
            analysis['oil_rate_trend'] = oil_trend
            analysis['oil_rate_slope'] = float(oil_slope)
            analysis['oil_rate_magnitude'] = TrendAnalyzer.classify_magnitude(oil_slope, oil_series)
            analysis['oil_rate_flag'] = oil_trend == 'decreasing'

            if analysis['oil_rate_flag'] and analysis['oil_rate_magnitude']:
                magnitude_factor = MAGNITUDE_FACTOR.get(analysis['oil_rate_magnitude'], 1)
                score += 1 * magnitude_factor * weights.oil_rate_weight

        # Analyze GLR (should be DECREASING = bad)
        glr_series = get_series('Form.GLR (scf/bbl)')
        glr_series_clean = [v for v in glr_series if v is not None]
        if len(glr_series_clean) >= 3:
            glr_trend, tau = TrendAnalyzer.mann_kendall_test(glr_series)
            glr_slope = TrendAnalyzer.sen_slope(glr_series)
            analysis['glr_trend'] = glr_trend
            analysis['glr_slope'] = float(glr_slope)
            analysis['glr_magnitude'] = TrendAnalyzer.classify_magnitude(glr_slope, glr_series)
            analysis['glr_flag'] = glr_trend == 'decreasing'

            if analysis['glr_flag'] and analysis['glr_magnitude']:
                magnitude_factor = MAGNITUDE_FACTOR.get(analysis['glr_magnitude'], 1)
                score += 1 * magnitude_factor * weights.glr_weight

        # Analyze Tubing Pressure (declining = potential issue)
        tp_series = get_series('Tubing Pressure (psi)')
        tp_series_clean = [v for v in tp_series if v is not None]
        if len(tp_series_clean) >= 3:
            tp_trend, tau = TrendAnalyzer.mann_kendall_test(tp_series)
            tp_slope = TrendAnalyzer.sen_slope(tp_series)
            analysis['tubing_pressure_trend'] = tp_trend
            analysis['tubing_pressure_slope'] = float(tp_slope)
            analysis['tubing_pressure_magnitude'] = TrendAnalyzer.classify_magnitude(tp_slope, tp_series)

            if tp_trend == 'decreasing' and analysis['tubing_pressure_magnitude']:
                magnitude_factor = MAGNITUDE_FACTOR.get(analysis['tubing_pressure_magnitude'], 1)
                score += 1 * magnitude_factor * weights.tubing_pressure_weight

        analysis['candidate_score'] = score

        return analysis


class SummaryGenerator:
    """Generate plain English summaries of analysis results"""

    @staticmethod
    def generate_comment(trend_data):
        """Generate summary comment for a well"""
        comments = []

        # BSW analysis
        if trend_data.get('bsw_flag'):
            bsw_mag = trend_data.get('bsw_magnitude', 'slightly')
            comments.append(f"BSW is {bsw_mag} trending up")

        # Oil rate analysis
        if trend_data.get('oil_rate_flag'):
            oil_mag = trend_data.get('oil_rate_magnitude', 'slightly')
            comments.append(f"oil rate is {oil_mag} declining")

        # GLR analysis
        if trend_data.get('glr_flag'):
            glr_mag = trend_data.get('glr_magnitude', 'slightly')
            comments.append(f"GLR is {glr_mag} declining")

        # Tubing Pressure analysis
        if trend_data.get('tubing_pressure_trend') == 'decreasing':
            tp_mag = trend_data.get('tubing_pressure_magnitude', 'slightly')
            comments.append(f"tubing pressure is {tp_mag} declining")

        if not comments:
            return "Does not show clear adverse production or fluid trends."

        comment = " and ".join(comments)
        return f"{comment.capitalize()}."