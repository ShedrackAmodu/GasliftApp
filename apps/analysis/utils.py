import statistics
import logging
import math
import copy
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
    variance = (2 * (2 * n + 5)) / (9 * n * (n - 1))
    if variance <= 0:
        return tau, 1.0

    z = tau / (variance ** 0.5)
    p_value = _normal_cdf(-abs(z)) * 2

    return tau, p_value


def _normal_cdf(x):
    """Approximate standard normal CDF using the Hastings approximation."""
    if x < 0:
        return 1 - _normal_cdf(-x)

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
    def filter_outliers(series, method='iqr', threshold=1.5):
        """
        Filter outliers from a numeric series using IQR or Hampel filter.
        Returns: (cleaned_series, rejected_indices)
        """
        import numpy as np
        cleaned = []
        rejected_indices = []
        
        # Convert to numpy array, preserving None positions
        arr = np.array([x if x is not None else np.nan for x in series], dtype=float)
        
        if method == 'iqr':
            # IQR method
            q1 = np.nanpercentile(arr, 25)
            q3 = np.nanpercentile(arr, 75)
            iqr = q3 - q1
            lower_bound = q1 - threshold * iqr
            upper_bound = q3 + threshold * iqr
            
            for idx, val in enumerate(arr):
                if np.isnan(val):
                    cleaned.append(None)
                elif val < lower_bound or val > upper_bound:
                    rejected_indices.append(idx)
                    cleaned.append(None)
                else:
                    cleaned.append(float(val))
        
        elif method == 'hampel':
            # Hampel filter (median absolute deviation)
            median = np.nanmedian(arr)
            mad = np.nanmedian(np.abs(arr - median))
            if mad == 0:
                mad = 1e-10  # avoid division by zero
            threshold_mad = threshold * mad * 1.4826  # 1.4826 for normal distribution
            
            for idx, val in enumerate(arr):
                if np.isnan(val):
                    cleaned.append(None)
                elif abs(val - median) > threshold_mad:
                    rejected_indices.append(idx)
                    cleaned.append(None)
                else:
                    cleaned.append(float(val))
        
        return cleaned, rejected_indices

    @staticmethod
    def calculate_data_quality_score(series):
        """
        Calculate data quality score (percentage of non-null values).
        """
        if not series:
            return 100.0
        valid_count = sum(1 for v in series if v is not None)
        return round((valid_count / len(series)) * 100, 2)

    @staticmethod
    def mann_kendall_test(data_series, time_series=None):
        """
        Perform Mann-Kendall trend test on a numeric list.
        Returns: trend direction, tau, p_value.
        """
        clean_pairs = []
        if time_series is not None:
            for t, v in zip(time_series, data_series):
                if v is not None and v != '' and t is not None:
                    clean_pairs.append((t, float(v)))
        else:
            for idx, v in enumerate(data_series):
                if v is not None and v != '':
                    clean_pairs.append((idx, float(v)))

        if len(clean_pairs) < 3:
            return 'no_trend', 0, 1.0

        x_vals = []
        y_vals = []
        first_time = clean_pairs[0][0]
        for t, v in clean_pairs:
            if hasattr(t, 'timestamp'):
                x_vals.append((t - first_time).total_seconds())
            else:
                x_vals.append(float(t))
            y_vals.append(v)

        tau, p_value = _kendall_tau(x_vals, y_vals)

        if p_value > 0.05:
            return 'no_trend', tau, p_value

        return ('increasing' if tau > 0 else 'decreasing'), tau, p_value

    @staticmethod
    def sen_slope(data_series, time_series=None):
        """
        Calculate Sen's slope estimator using actual time spacing.
        Returns: slope value per unit time.
        """
        clean_pairs = []
        if time_series is not None:
            for t, v in zip(time_series, data_series):
                if v is not None and v != '' and t is not None:
                    clean_pairs.append((t, float(v)))
        else:
            for idx, v in enumerate(data_series):
                if v is not None and v != '':
                    clean_pairs.append((idx, float(v)))

        if len(clean_pairs) < 3:
            return 0

        slopes = []
        for i in range(len(clean_pairs) - 1):
            x_i, y_i = clean_pairs[i]
            for j in range(i + 1, len(clean_pairs)):
                x_j, y_j = clean_pairs[j]
                if hasattr(x_i, 'timestamp') and hasattr(x_j, 'timestamp'):
                    delta_t = (x_j - x_i).total_seconds() / 86400.0
                else:
                    delta_t = float(x_j) - float(x_i)
                if delta_t == 0:
                    continue
                slopes.append((y_j - y_i) / delta_t)

        if slopes:
            return statistics.median(slopes)
        return 0

    @staticmethod
    def classify_magnitude(slope, data_series):
        """Classify magnitude of trend as Slightly, Moderately, or Aggressively"""
        if slope == 0:
            return None

        clean_values = [float(v) for v in data_series if v is not None and v != '']
        if len(clean_values) < 2:
            return 'slightly'

        reference = abs(statistics.mean(clean_values))
        if reference == 0:
            return 'slightly'

        relative_change = abs(slope) / reference

        if relative_change < 0.005:
            return 'slightly'
        elif relative_change < 0.02:
            return 'moderately'
        else:
            return 'aggressively'

    @staticmethod
    def analyze_well(well_data, weights, base_choke_size=None, choke_exponent=0.5,
                     outlier_method='iqr', outlier_threshold=1.5):
        """
        Analyze a single well's trends using the full scoring methodology.
        `well_data` is a list of dicts (rows), sorted by date.
        
        Parameters:
            base_choke_size: Choke size for normalization (e.g., "24/64")
            choke_exponent: Choke normalization exponent
            outlier_method: 'iqr' or 'hampel'
            outlier_threshold: Multiplier for outlier detection

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
            # Data quality
            'data_quality_score': 100.0,
            'outlier_count': 0,
            'rejected_indices': {'bsw': [], 'oil_rate': [], 'glr': [], 'tp': []},
            # Original and corrected values for charts
            'original_values': {},
            'corrected_values': {},
            # Additional well metadata
            'prod_method': '',
            'test_status': '',
            'flow_line_pressure': 0,
            'well_choke_size': '',
            'is_choke_normalized': False,
        }

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

        # Store raw original values for chart display
        original_bsw = [r.get('BS&W (%)') for r in well_data]
        original_oil = [r.get('Net Oil (bopd)') for r in well_data]
        original_glr = [r.get('Form.GLR (scf/bbl)') for r in well_data]
        original_tp = [r.get('Tubing Pressure (psi)') for r in well_data]
        
        analysis['original_values'] = {
            'bsw': original_bsw,
            'oil_rate': original_oil,
            'glr': original_glr,
            'tp': original_tp,
        }

        def get_series(field, orig_series, key):
            # Prefer corrected series when choke normalization applied
            corrected_field = f"corrected_{field}"
            series = []
            for r in well_data:
                if corrected_field in r and r.get(corrected_field) is not None:
                    series.append(r.get(corrected_field))
                else:
                    series.append(r.get(field))
            
            # Apply outlier filtering
            if outlier_method and series:
                filtered, rejected = TrendAnalyzer.filter_outliers(series, method=outlier_method, threshold=outlier_threshold)
                analysis['rejected_indices'][key] = rejected
                analysis['outlier_count'] += len(rejected)
                return filtered
            return series

        def corrected_series_exists(field):
            corrected_field = f"corrected_{field}"
            return any(r.get(corrected_field) is not None for r in well_data)

        def get_time_series():
            return [r.get('Date') for r in well_data]

        def apply_choke_normalization(series):
            """Normalize series to base choke size using area scaling"""
            if not base_choke_size:
                return series, False
            
            base_d = TrendAnalyzer.parse_choke_size(base_choke_size)
            if base_d is None:
                return series, False
            
            area_base = TrendAnalyzer._choke_area_inches2(base_d)
            if area_base is None:
                return series, False
            
            corrected = []
            for idx, r in enumerate(well_data):
                actual = r.get('Well Choke Size')
                actual_d = TrendAnalyzer.parse_choke_size(actual)
                if actual_d is None:
                    corrected.append(series[idx])
                    continue
                area_actual = TrendAnalyzer._choke_area_inches2(actual_d)
                if area_actual is None or area_actual == 0:
                    corrected.append(series[idx])
                    continue
                try:
                    factor = (area_base / area_actual) ** float(choke_exponent)
                    val = series[idx]
                    corrected.append(float(val) * factor if val is not None else None)
                except Exception:
                    corrected.append(series[idx])
            return corrected, True

        score = 0
        time_series = get_time_series()
        analysis['is_choke_normalized'] = base_choke_size is not None

        # BSW
        bsw_series = get_series('BS&W (%)', original_bsw, 'bsw')
        if base_choke_size and not corrected_series_exists('BS&W (%)'):
            bsw_series, _ = apply_choke_normalization(bsw_series)
        analysis['corrected_values']['bsw'] = bsw_series
        
        if len([v for v in bsw_series if v is not None]) >= 3:
            bsw_trend, tau, p_value = TrendAnalyzer.mann_kendall_test(bsw_series, time_series=time_series)
            bsw_slope = TrendAnalyzer.sen_slope(bsw_series, time_series=time_series)
            analysis['bsw_trend'] = bsw_trend
            analysis['bsw_slope'] = float(bsw_slope)
            analysis['bsw_magnitude'] = TrendAnalyzer.classify_magnitude(bsw_slope, bsw_series)
            analysis['bsw_flag'] = bsw_trend == 'increasing'
            magnitude_factor = MAGNITUDE_FACTOR.get(analysis['bsw_magnitude'], 1)
            if analysis['bsw_flag']:
                score += abs(bsw_slope) * magnitude_factor * weights.bsw_weight

        # Oil Rate
        oil_series = get_series('Net Oil (bopd)', original_oil, 'oil_rate')
        if base_choke_size and not corrected_series_exists('Net Oil (bopd)'):
            oil_series, _ = apply_choke_normalization(oil_series)
        analysis['corrected_values']['oil_rate'] = oil_series
        
        if len([v for v in oil_series if v is not None]) >= 3:
            oil_trend, tau, p_value = TrendAnalyzer.mann_kendall_test(oil_series, time_series=time_series)
            oil_slope = TrendAnalyzer.sen_slope(oil_series, time_series=time_series)
            analysis['oil_rate_trend'] = oil_trend
            analysis['oil_rate_slope'] = float(oil_slope)
            analysis['oil_rate_magnitude'] = TrendAnalyzer.classify_magnitude(oil_slope, oil_series)
            analysis['oil_rate_flag'] = oil_trend == 'decreasing'
            magnitude_factor = MAGNITUDE_FACTOR.get(analysis['oil_rate_magnitude'], 1)
            if analysis['oil_rate_flag']:
                score += abs(oil_slope) * magnitude_factor * weights.oil_rate_weight

        # GLR
        glr_series = get_series('Form.GLR (scf/bbl)', original_glr, 'glr')
        if base_choke_size and not corrected_series_exists('Form.GLR (scf/bbl)'):
            glr_series, _ = apply_choke_normalization(glr_series)
        analysis['corrected_values']['glr'] = glr_series
        
        if len([v for v in glr_series if v is not None]) >= 3:
            glr_trend, tau, p_value = TrendAnalyzer.mann_kendall_test(glr_series, time_series=time_series)
            glr_slope = TrendAnalyzer.sen_slope(glr_series, time_series=time_series)
            analysis['glr_trend'] = glr_trend
            analysis['glr_slope'] = float(glr_slope)
            analysis['glr_magnitude'] = TrendAnalyzer.classify_magnitude(glr_slope, glr_series)
            analysis['glr_flag'] = glr_trend == 'decreasing'
            magnitude_factor = MAGNITUDE_FACTOR.get(analysis['glr_magnitude'], 1)
            if analysis['glr_flag']:
                score += abs(glr_slope) * magnitude_factor * weights.glr_weight

        # Tubing Pressure
        tp_series = get_series('Tubing Pressure (psi)', original_tp, 'tp')
        if base_choke_size and not corrected_series_exists('Tubing Pressure (psi)'):
            tp_series, _ = apply_choke_normalization(tp_series)
        analysis['corrected_values']['tp'] = tp_series
        
        if len([v for v in tp_series if v is not None]) >= 3:
            tp_trend, tau, p_value = TrendAnalyzer.mann_kendall_test(tp_series, time_series=time_series)
            tp_slope = TrendAnalyzer.sen_slope(tp_series, time_series=time_series)
            analysis['tubing_pressure_trend'] = tp_trend
            analysis['tubing_pressure_slope'] = float(tp_slope)
            analysis['tubing_pressure_magnitude'] = TrendAnalyzer.classify_magnitude(tp_slope, tp_series)
            magnitude_factor = MAGNITUDE_FACTOR.get(analysis['tubing_pressure_magnitude'], 1)
            if tp_trend == 'decreasing':
                score += abs(tp_slope) * magnitude_factor * weights.tubing_pressure_weight

        # Calculate data quality score
        all_series = bsw_series + oil_series + glr_series + tp_series
        analysis['data_quality_score'] = TrendAnalyzer.calculate_data_quality_score(all_series)

        analysis['candidate_score'] = round(score, 6)

        return analysis

    @staticmethod
    def parse_choke_size(choke_str):
        """
        Parse choke size strings like '24/64"' or '0.375' and return inches as float.
        Returns None if parsing fails.
        """
        if choke_str is None:
            return None
        try:
            s = str(choke_str).strip().replace('"', '').replace('\u201d', '')
            # handle fractional e.g. 24/64
            if '/' in s:
                parts = s.split('/')
                if len(parts) == 2:
                    num = float(parts[0])
                    den = float(parts[1])
                    if den != 0:
                        return num / den
            # otherwise try float
            return float(s)
        except Exception:
            return None

    @staticmethod
    def _choke_area_inches2(diameter_inch):
        """Return choke opening area in square inches for a diameter in inches."""
        if diameter_inch is None or diameter_inch <= 0:
            return None
        return math.pi * (diameter_inch ** 2) / 4.0

    @staticmethod
    def apply_choke_normalization(well_data, base_choke_size, exponent=0.5,
                                   choke_field='Well Choke Size',
                                   fields_to_correct=None):
        """
        Return a deep-copied list of rows where the rate fields are normalized to
        `base_choke_size` (inches). The normalization uses area scaling to the
        provided exponent: corrected = raw * (area_base / area_actual) ** exponent.
        """
        if fields_to_correct is None:
            fields_to_correct = ['Net Oil (bopd)', 'Form.GLR (scf/bbl)']

        base_d = TrendAnalyzer.parse_choke_size(base_choke_size)
        if base_d is None:
            return well_data

        area_base = TrendAnalyzer._choke_area_inches2(base_d)
        if area_base is None:
            return well_data

        data_copy = copy.deepcopy(well_data)
        for row in data_copy:
            actual = row.get(choke_field)
            actual_d = TrendAnalyzer.parse_choke_size(actual)
            if actual_d is None:
                # cannot normalize this row
                continue
            area_actual = TrendAnalyzer._choke_area_inches2(actual_d)
            if area_actual is None or area_actual == 0:
                continue

            try:
                factor = (area_base / area_actual) ** float(exponent)
            except Exception:
                factor = 1.0

            for f in fields_to_correct:
                raw = row.get(f)
                try:
                    if raw is None or raw == '':
                        continue
                    corrected = float(raw) * factor
                    row[f'corrected_{f}'] = corrected
                except (ValueError, TypeError):
                    # leave unmodified if cannot parse
                    continue

        return data_copy


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
        elif trend_data.get('glr_trend') == 'no_trend':
            comments.append("GLR is stable")

        # Tubing Pressure analysis
        if trend_data.get('tubing_pressure_trend') == 'decreasing':
            tp_mag = trend_data.get('tubing_pressure_magnitude', 'slightly')
            comments.append(f"tubing pressure is {tp_mag} declining")
        elif trend_data.get('tubing_pressure_trend') == 'increasing':
            tp_mag = trend_data.get('tubing_pressure_magnitude', 'slightly')
            comments.append(f"tubing pressure is {tp_mag} increasing")

        # Liquid loading and efficiency
        if trend_data.get('liquid_loading_flag'):
            comments.append("liquid loading detected")
        if trend_data.get('recommended_gas_mmscf') is not None:
            comments.append(f"recommended gas {trend_data['recommended_gas_mmscf']:.2f} MMscf/d")

        # Economic urgency
        if trend_data.get('days_to_economic_limit') is not None:
            days = trend_data['days_to_economic_limit']
            if days <= 90:
                comments.append("urgent action recommended")
            elif days <= 180:
                comments.append("near-term attention advised")
            else:
                comments.append("economic limit is not imminent")

        # Completion feasibility
        if trend_data.get('completion_feasibility') == 'requires_deepening':
            comments.append("completion requires tubing deepening")
        elif trend_data.get('completion_feasibility') == 'pressure_limited':
            comments.append("pressure limits completion feasibility")
        elif trend_data.get('completion_feasibility') == 'feasible':
            comments.append("completion looks feasible")

        if not comments:
            return "Does not show clear adverse production or fluid trends."

        comment = "; ".join(comments)
        return f"{comment.capitalize()}."