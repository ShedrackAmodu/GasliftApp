"""
Monte Carlo Sensitivity Analysis for probabilistic ranking.
"""
import random
import statistics
from .utils import TrendAnalyzer, SummaryGenerator


class MonteCarloSensitivity:
    """
    Run Monte Carlo simulations to determine rank distribution
    by randomly perturbing weights within ±20%.
    """
    
    DEFAULT_ITERATIONS = 1000
    PERTURBATION_FACTOR = 0.20  # ±20%
    
    def __init__(self, iterations=DEFAULT_ITERATIONS):
        self.iterations = iterations
    
    def _perturb_weight(self, base_weight):
        """Randomly perturb a weight within ±20%"""
        if base_weight <= 0:
            return 0
        factor = 1.0 + random.uniform(-self.PERTURBATION_FACTOR, self.PERTURBATION_FACTOR)
        return max(0, base_weight * factor)
    
    def run_simulation(self, all_well_data, base_weights, 
                       base_choke_size=None, outlier_method='iqr', outlier_threshold=1.5):
        """
        Run N Monte Carlo simulations on all wells.
        
        Parameters:
            all_well_data: dict of {well_id: [list of row dicts]}
            base_weights: AnalysisWeights object with base weights
            base_choke_size: optional choke normalization
            outlier_method: outlier detection method
            outlier_threshold: outlier threshold multiplier
        
        Returns:
            dict of {well_id: {
                'rank_mean': float,
                'rank_std': float,
                'rank_5th': float,
                'rank_95th': float,
                'score_mean': float,
                'score_std': float,
                'rank_distribution': [list of ranks from each run],
            }}
        """
        from .models import AnalysisWeights
        
        results = {}
        score_history = {well_id: [] for well_id in all_well_data}
        
        for _ in range(self.iterations):
            # Create perturbed weights
            perturbed_weights = AnalysisWeights(
                bsw_weight=self._perturb_weight(base_weights.bsw_weight),
                oil_rate_weight=self._perturb_weight(base_weights.oil_rate_weight),
                glr_weight=self._perturb_weight(base_weights.glr_weight),
                tubing_pressure_weight=self._perturb_weight(base_weights.tubing_pressure_weight),
            )
            
            # Score all wells
            well_scores = []
            for well_id, well_rows in all_well_data.items():
                trends = TrendAnalyzer.analyze_well(
                    well_rows, perturbed_weights,
                    base_choke_size=base_choke_size,
                    outlier_method=outlier_method,
                    outlier_threshold=outlier_threshold,
                )
                score_history[well_id].append(trends['candidate_score'])
            
            # Rank wells for this iteration
            sorted_scores = sorted(score_history.items(), key=lambda x: x[1][-1], reverse=True)
            for rank, (well_id, _) in enumerate(sorted_scores, 1):
                if well_id not in results:
                    results[well_id] = {'ranks': [], 'scores': []}
                results[well_id]['ranks'].append(rank)
                results[well_id]['scores'].append(score_history[well_id][-1])
        
        # Calculate statistics
        final_results = {}
        for well_id, data in results.items():
            ranks = data['ranks']
            scores = data['scores']
            
            rank_mean = statistics.mean(ranks)
            rank_std = statistics.stdev(ranks) if len(ranks) > 1 else 0
            score_mean = statistics.mean(scores)
            score_std = statistics.stdev(scores) if len(scores) > 1 else 0
            
            # Percentiles
            sorted_ranks = sorted(ranks)
            rank_5th = sorted_ranks[int(len(sorted_ranks) * 0.05)]
            rank_95th = sorted_ranks[int(len(sorted_ranks) * 0.95)]
            
            final_results[well_id] = {
                'rank_mean': round(rank_mean, 2),
                'rank_std': round(rank_std, 2),
                'rank_5th': rank_5th,
                'rank_95th': rank_95th,
                'score_mean': round(score_mean, 2),
                'score_std': round(score_std, 2),
                # Sample distribution for box-plot (every 10th value)
                'rank_distribution': ranks[::10],  # 100 points for chart
                'rank_variance': round(rank_std / max(rank_mean, 0.01), 3),
            }
        
        return final_results
    
    @staticmethod
    def classify_confidence(rank_variance):
        """Classify decision confidence based on rank variance"""
        if rank_variance < 0.15:
            return 'no_brainer'
        elif rank_variance < 0.30:
            return 'confident'
        elif rank_variance < 0.50:
            return 'uncertain'
        else:
            return 'requires_engineering_judgement'