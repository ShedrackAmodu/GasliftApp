import pandas as pd
import numpy as np
from scipy.stats import kendalltau
import logging
from .models import WellTrendAnalysis, AnalysisWeights

logger = logging.getLogger(__name__)

# Map magnitude descriptors to numeric factors for scoring
MAGNITUDE_FACTOR = {
    'slightly': 1,
    'moderately': 2,
    'aggressively': 3,
}

class TrendAnalyzer:
    """Analyzes well trends using Mann-Kendall and Sen's slope"""
    
    @staticmethod
    def mann_kendall_test(data):
        """
        Perform Mann-Kendall trend test
        Returns: trend direction (increasing, decreasing, no_trend)
        """
        if len(data) < 3:
            return 'no_trend', 0
        
        # Remove NaN values
        data_clean = data.dropna()
        if len(data_clean) < 3:
            return 'no_trend', 0
        
        # Perform Mann-Kendall test
        tau, p_value = kendalltau(range(len(data_clean)), data_clean.values)
        
        # Significance level
        if p_value > 0.05:
            return 'no_trend', tau
        
        if tau > 0:
            return 'increasing', tau
        else:
            return 'decreasing', tau
    
    @staticmethod
    def sen_slope(data):
        """
        Calculate Sen's slope estimator
        Returns: slope value (rate of change)
        """
        if len(data) < 3:
            return 0
        
        data_clean = data.dropna()
        if len(data_clean) < 3:
            return 0
        
        n = len(data_clean)
        slopes = []
        
        for i in range(n - 1):
            for j in range(i + 1, n):
                slope = (data_clean.iloc[j] - data_clean.iloc[i]) / (j - i)
                slopes.append(slope)
        
        if slopes:
            return np.median(slopes)
        return 0
    
    @staticmethod
    def classify_magnitude(slope, data):
        """Classify magnitude of trend as Slightly, Moderately, or Aggressively"""
        if slope == 0:
            return None
        
        # Calculate relative change over range
        data_clean = data.dropna()
        if len(data_clean) < 2:
            return 'slightly'
        
        data_range = data_clean.max() - data_clean.min()
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
        Analyze a single well's trends using the full scoring methodology:
        - trend_score = (trend_direction_sign) × (magnitude_factor) × (weight)
        - BSW: increasing is bad (sign=1 if increasing)
        - Oil Rate: decreasing is bad (sign=1 if decreasing)
        - GLR: decreasing is bad (sign=1 if decreasing)
        - Tubing Pressure: decreasing can indicate issues (sign=1 if decreasing)
        
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
        if 'Prod Method' in well_data.columns:
            valid_methods = well_data['Prod Method'].dropna()
            if not valid_methods.empty:
                analysis['prod_method'] = str(valid_methods.iloc[-1])
        if 'Test Status' in well_data.columns:
            valid_statuses = well_data['Test Status'].dropna()
            if not valid_statuses.empty:
                analysis['test_status'] = str(valid_statuses.iloc[-1])
        if 'Flow Line Pressure (psi)' in well_data.columns:
            valid_flp = well_data['Flow Line Pressure (psi)'].dropna()
            if not valid_flp.empty:
                analysis['flow_line_pressure'] = float(valid_flp.iloc[-1])
        if 'Well Choke Size' in well_data.columns:
            valid_choke = well_data['Well Choke Size'].dropna()
            if not valid_choke.empty:
                analysis['well_choke_size'] = str(valid_choke.iloc[-1])
        
        score = 0
        
        # Analyze BSW (should be INCREASING = bad)
        if 'BS&W (%)' in well_data.columns:
            bsw_trend, tau = TrendAnalyzer.mann_kendall_test(well_data['BS&W (%)'])
            bsw_slope = TrendAnalyzer.sen_slope(well_data['BS&W (%)'])
            analysis['bsw_trend'] = bsw_trend
            analysis['bsw_slope'] = float(bsw_slope)
            analysis['bsw_magnitude'] = TrendAnalyzer.classify_magnitude(bsw_slope, well_data['BS&W (%)'])
            analysis['bsw_flag'] = bsw_trend == 'increasing'
            
            # Score = direction_sign × magnitude_factor × weight
            if analysis['bsw_flag'] and analysis['bsw_magnitude']:
                magnitude_factor = MAGNITUDE_FACTOR.get(analysis['bsw_magnitude'], 1)
                score += 1 * magnitude_factor * weights.bsw_weight
        
        # Analyze Oil Rate (should be DECREASING = bad)
        if 'Net Oil (bopd)' in well_data.columns:
            oil_trend, tau = TrendAnalyzer.mann_kendall_test(well_data['Net Oil (bopd)'])
            oil_slope = TrendAnalyzer.sen_slope(well_data['Net Oil (bopd)'])
            analysis['oil_rate_trend'] = oil_trend
            analysis['oil_rate_slope'] = float(oil_slope)
            analysis['oil_rate_magnitude'] = TrendAnalyzer.classify_magnitude(oil_slope, well_data['Net Oil (bopd)'])
            analysis['oil_rate_flag'] = oil_trend == 'decreasing'
            
            # Score = direction_sign × magnitude_factor × weight
            if analysis['oil_rate_flag'] and analysis['oil_rate_magnitude']:
                magnitude_factor = MAGNITUDE_FACTOR.get(analysis['oil_rate_magnitude'], 1)
                score += 1 * magnitude_factor * weights.oil_rate_weight
        
        # Analyze GLR (should be DECREASING = bad)
        if 'Form.GLR (scf/bbl)' in well_data.columns:
            glr_trend, tau = TrendAnalyzer.mann_kendall_test(well_data['Form.GLR (scf/bbl)'])
            glr_slope = TrendAnalyzer.sen_slope(well_data['Form.GLR (scf/bbl)'])
            analysis['glr_trend'] = glr_trend
            analysis['glr_slope'] = float(glr_slope)
            analysis['glr_magnitude'] = TrendAnalyzer.classify_magnitude(glr_slope, well_data['Form.GLR (scf/bbl)'])
            analysis['glr_flag'] = glr_trend == 'decreasing'
            
            # Score = direction_sign × magnitude_factor × weight
            if analysis['glr_flag'] and analysis['glr_magnitude']:
                magnitude_factor = MAGNITUDE_FACTOR.get(analysis['glr_magnitude'], 1)
                score += 1 * magnitude_factor * weights.glr_weight
        
        # Analyze Tubing Pressure (declining = potential issue)
        if 'Tubing Pressure (psi)' in well_data.columns:
            tp_trend, tau = TrendAnalyzer.mann_kendall_test(well_data['Tubing Pressure (psi)'])
            tp_slope = TrendAnalyzer.sen_slope(well_data['Tubing Pressure (psi)'])
            analysis['tubing_pressure_trend'] = tp_trend
            analysis['tubing_pressure_slope'] = float(tp_slope)
            analysis['tubing_pressure_magnitude'] = TrendAnalyzer.classify_magnitude(tp_slope, well_data['Tubing Pressure (psi)'])
            
            # Score = direction_sign × magnitude_factor × weight
            # For tubing pressure, decreasing is a potential issue
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