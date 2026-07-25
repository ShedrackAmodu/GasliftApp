"""
IPR (Inflow Performance Relationship) and reservoir engineering calculations.
"""
import math

class IPRCalculator:
    """Calculate Productivity Index and reservoir parameters"""
    
    @staticmethod
    def calculate_pi(oil_rate_bopd, static_reservoir_pressure_psi, flowing_bhp_psi):
        """
        Calculate Productivity Index (PI) in bopd/psi
        
        Parameters:
            oil_rate_bopd: Oil production rate (bopd)
            static_reservoir_pressure_psi: Static/reservoir pressure (psi)
            flowing_bhp_psi: Flowing bottom-hole pressure (psi)
        
        Returns:
            PI in bopd/psi, or None if inputs invalid
        """
        try:
            if static_reservoir_pressure_psi is None or flowing_bhp_psi is None:
                return None
            if static_reservoir_pressure_psi <= flowing_bhp_psi:
                return None
            drawdown = static_reservoir_pressure_psi - flowing_bhp_psi
            if drawdown <= 0:
                return None
            pi = oil_rate_bopd / drawdown
            return round(pi, 4)
        except Exception:
            return None
    
    @staticmethod
    def calculate_drawdown_stability(pi_values, time_series):
        """
        Determine if PI is declining (formation damage) or stable
        
        Parameters:
            pi_values: List of PI values over time
            time_series: List of datetime or numeric values
        
        Returns:
            trend: 'declining', 'stable', 'increasing', or 'no_trend'
            slope: Sen's slope estimate
        """
        if not pi_values or len(pi_values) < 3:
            return 'no_trend', 0
        
        # Simple linear regression for trend detection
        clean_pairs = [(t, pi) for t, pi in zip(time_series, pi_values) if pi is not None]
        if len(clean_pairs) < 3:
            return 'no_trend', 0
        
        # Calculate slope using least squares
        n = len(clean_pairs)
        x_vals = [i for i in range(n)]  # Use index if time not numeric
        y_vals = [p[1] for p in clean_pairs]
        
        mean_x = sum(x_vals) / n
        mean_y = sum(y_vals) / n
        
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals))
        denominator = sum((x - mean_x) ** 2 for x in x_vals)
        
        if denominator == 0:
            return 'no_trend', 0
        
        slope = numerator / denominator
        
        # Determine if slope is significant (>5% decline per time unit)
        if abs(slope) < 0.01 * abs(mean_y):
            return 'stable', slope
        elif slope < 0:
            return 'declining', slope
        else:
            return 'increasing', slope
    
    @staticmethod
    def estimate_reservoir_pressure_vog(true_reservoir_pressure_psi, oil_rate_bopd, pi_bopd_psi, 
                                         drainage_area_acres, porosity, thickness_ft, formation_volume_factor,
                                         viscosity_cp=None):
        """
        Estimate reservoir pressure using Vogel IPR (for solution-gas drive reservoirs)
        
        Vogel (1969): J = (q_max / (P_r - P_wf)) * (1 - 0.2 * (P_wf/P_r) - 0.8 * (P_wf/P_r)^2)
        
        Parameters:
            true_reservoir_pressure_psi: Average reservoir pressure (psi)
            oil_rate_bopd: Current oil rate
            pi_bopd_psi: Productivity Index at current conditions
            drainage_area_acres: Drainage area (acres)
            porosity: Formation porosity (fraction)
            thickness_ft: Net pay thickness (ft)
            formation_volume_factor: Oil FVF (bbl/STB)
            viscosity_cp: Oil viscosity (cp) - optional
        
        Returns:
            dict with estimated reservoir pressure and q_max
        """
        try:
            if true_reservoir_pressure_psi is None or pi_bopd_psi is None:
                return None
            
            # Simplified: use PI and rate
            # q_max = PI * P_r * 0.8 (approximate from Vogel at P_wf=0)
            q_max = pi_bopd_psi * true_reservoir_pressure_psi * 0.8
            
            return {
                'estimated_reservoir_pressure': true_reservoir_pressure_psi,
                'q_max': round(q_max, 2),
                'pi': pi_bopd_psi
            }
        except Exception:
            return None
    
    @staticmethod
    def calculate_drawdown(static_reservoir_pressure_psi, flowing_bhp_psi):
        """Calculate drawdown pressure"""
        try:
            if static_reservoir_pressure_psi is None or flowing_bhp_psi is None:
                return None
            return static_reservoir_pressure_psi - flowing_bhp_psi
        except Exception:
            return None


class LiquidLoadingDiagnostics:
    """Diagnose liquid loading conditions"""
    
    def __init__(self, pvt_properties, tubing_diameter_inch):
        """
        Parameters:
            pvt_properties: PVTProperties instance
            tubing_diameter_inch: Tubing inside diameter
        """
        self.pvt = pvt_properties
        self.tubing_diameter = tubing_diameter_inch
    
    def analyze_well(self, avg_glr_scf_bbl, avg_tubing_pressure_psi, gas_rate_mmscfd=None, oil_rate_bopd=None):
        """
        Analyze if well is liquid loaded
        
        Parameters:
            avg_glr_scf_bbl: Average GLR
            avg_tubing_pressure_psi: Average tubing pressure (psi)
            gas_rate_mmscfd: Gas rate (optional, overrides calculation from GLR)
            oil_rate_bopd: Oil rate used to estimate gas rate from GLR when gas rate is not provided
        
        Returns:
            dict with liquid loading diagnosis
        """
        result = {
            'liquid_loading_flag': False,
            'critical_glr': None,
            'actual_glr': avg_glr_scf_bbl,
            'critical_velocity': None,
            'actual_velocity': None,
            'diagnosis': 'Unknown'
        }
        
        try:
            # Calculate critical GLR using Turner criteria
            # Simplified approach: compare actual GLR to critical GLR
            
            # Critical velocity calculation
            v_critical = self.pvt.calculate_critical_velocity_turner(
                avg_tubing_pressure_psi,
                self.tubing_diameter
            )
            result['critical_velocity'] = v_critical
            
            # Actual gas velocity calculation
            estimated_gas_rate = None
            if gas_rate_mmscfd is None and oil_rate_bopd is not None and oil_rate_bopd > 0 and avg_glr_scf_bbl is not None and avg_glr_scf_bbl > 0:
                estimated_gas_rate = (avg_glr_scf_bbl * oil_rate_bopd) / 1_000_000.0

            if gas_rate_mmscfd is None:
                gas_rate_mmscfd = estimated_gas_rate if estimated_gas_rate and estimated_gas_rate > 0 else 2.0

            result['gas_rate_mmscfd'] = gas_rate_mmscfd
            result['actual_glr'] = avg_glr_scf_bbl

            v_actual = self.pvt.calculate_actual_gas_velocity(
                gas_rate_mmscfd,
                self.tubing_diameter,
                avg_tubing_pressure_psi
            )
            result['actual_velocity'] = v_actual

            if v_actual > 0 and v_critical > 0:
                result['gas_utilization_efficiency'] = min(100.0, max(0.0, (v_actual / v_critical) * 100.0))
                result['critical_glr'] = round(avg_glr_scf_bbl * (v_critical / max(v_actual, 1e-6)), 2) if avg_glr_scf_bbl is not None else None
            else:
                result['critical_glr'] = avg_glr_scf_bbl

            if gas_rate_mmscfd and gas_rate_mmscfd > 0:
                result['recommended_gas_mmscf'] = round(gas_rate_mmscfd * 0.4, 3)
            else:
                result['recommended_gas_mmscf'] = 0.5

            # Determine if liquid loaded
            if result['actual_velocity'] < result['critical_velocity']:
                result['liquid_loading_flag'] = True
                result['diagnosis'] = 'LIQUID LOADED - Gas lift recommended'
            else:
                result['liquid_loading_flag'] = False
                result['diagnosis'] = 'Not liquid loaded'

            return result
        except Exception as e:
            result['diagnosis'] = f'Error: {str(e)}'
            return result