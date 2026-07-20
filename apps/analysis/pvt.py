"""
PVT (Fluid Property) calculations for gas lift analysis.
"""
import math

class PVTProperties:
    """Container for PVT properties"""
    def __init__(self, api_gravity, gas_specific_gravity, water_salinity, temperature_f):
        self.api_gravity = api_gravity
        self.gas_specific_gravity = gas_specific_gravity
        self.water_salinity = water_salinity  # ppm
        self.temperature_f = temperature_f  # °F

    @property
    def oil_specific_gravity(self):
        """API gravity to specific gravity"""
        return 141.5 / (131.5 + self.api_gravity)

    @property
    def water_specific_gravity(self):
        """Approximate water SG from salinity"""
        return 1.0 + (self.water_salinity * 0.000007)  # simplified

    def standing_oil_formation_volume_factor(self, pressure_psi, solution_gas_oil_ratio_scf_bbl):
        """
        Standing correlation for oil formation volume factor (Bo)
        Returns Bo in reservoir bbl/STB
        """
        try:
            # Standing (1981)
            # F = (Rs * sqrt(gas_sg / oil_sg)) + 1.25 * temp_f
            F = solution_gas_oil_ratio_scf_bbl * math.sqrt(self.gas_specific_gravity / self.oil_specific_gravity)
            F += 1.25 * self.temperature_f
            
            # Bo = 0.9759 + 0.00012 * F^1.2
            Bo = 0.9759 + 0.00012 * (F ** 1.2)
            return max(Bo, 1.0)
        except Exception:
            return 1.0

    def glaso_oil_formation_volume_factor(self, pressure_psi, solution_gas_oil_ratio_scf_bbl):
        """
        Glaso correlation for oil formation volume factor
        More accurate than Standing for higher pressures
        """
        try:
            # Glaso (1980)
            log_bo = -0.012 + 0.00017 * pressure_psi + 0.00001 * (self.temperature_f ** 1.5)
            log_bo += 0.00019 * math.log10(self.gas_specific_gravity / self.oil_specific_gravity)
            log_bo += 0.00001 * solution_gas_oil_ratio_scf_bbl
            Bo = 10 ** log_bo
            return max(Bo, 1.0)
        except Exception:
            return 1.0

    def calculate_density(self, pressure_psi, solution_gas_oil_ratio_scf_bbl):
        """
        Calculate average fluid density in lb/ft³
        Mixture of oil, water, and gas
        """
        try:
            # Oil density at reservoir conditions
            oil_api = self.api_gravity
            oil_density_stb = (141.5 / (131.5 + oil_api)) * 62.4  # lb/ft³
            
            # Water density
            water_density = self.water_specific_gravity * 62.4  # lb/ft³
            
            # Gas density from real gas law (approximate using Z=0.9)
            z_factor = 0.9
            gas_constant = 10.732  # psi·ft³/(lb-mol·°R)
            temp_rankine = self.temperature_f + 459.67
            gas_density = (pressure_psi * self.gas_specific_gravity) / (z_factor * gas_constant * temp_rankine) * 62.4  # lb/ft³
            
            return {
                'oil_density': oil_density_stb,
                'water_density': water_density,
                'gas_density': gas_density,
                'mixture_density': oil_density_stb  # placeholder
            }
        except Exception:
            return {
                'oil_density': 52.0,
                'water_density': 62.4,
                'gas_density': 5.0,
                'mixture_density': 52.0
            }

    def calculate_z_factor(self, pressure_psi, temperature_f):
        """
        Estimate Z-factor (compressibility factor) using Hall-Yarborough
        """
        try:
            # Simplified correlation - would need full Hall-Yarborough for accuracy
            # Returns approximate Z
            t_pr = (temperature_f + 459.67) / (168 + 325 * self.gas_specific_gravity)  # reduced temp
            p_pr = pressure_psi / (677 + 15.0 * self.gas_specific_gravity - 37.5 * self.gas_specific_gravity ** 2)  # reduced pressure
            
            if t_pr <= 1.5:
                z = 1.0 - (3.52 * p_pr / (1.0 + 10.0 * p_pr ** 2)) / (10 ** (1.153 * t_pr))
            else:
                z = 1.0 - (3.52 * p_pr / (1.0 + 10.0 * p_pr ** 2)) / (10 ** (1.0 + 0.007 * (t_pr - 1.5)))
            
            return max(z, 0.1)
        except Exception:
            return 0.9

    def calculate_critical_velocity_turner(self, wellhead_pressure_psi, tubing_diameter_inch, 
                                            gas_gravity=None, temperature_f=None):
        """
        Calculate critical gas velocity for liquid loading using Turner et al. (1969) criteria.
        Liquid loading occurs when actual gas velocity < critical velocity.
        
        Parameters:
            wellhead_pressure_psi: Pressure at which to evaluate (psi)
            tubing_diameter_inch: Tubing inside diameter (inch)
            gas_gravity: Gas specific gravity (defaults to instance value)
            temperature_f: Temperature °F (defaults to instance value)
        
        Returns:
            critical_velocity (ft/s)
        """
        if gas_gravity is None:
            gas_gravity = self.gas_specific_gravity
        if temperature_f is None:
            temperature_f = self.temperature_f

        try:
            # Turner correlation parameters
            # droplet density: use oil density (assume water cut handled separately)
            oil_density_lbft3 = (141.5 / (131.5 + self.api_gravity)) * 62.4
            sigma_dyne_cm2 = 28 - 0.0003 * self.api_gravity  # interfacial tension
            
            # Convert to field units
            sigma_lbf_ft = sigma_dyne_cm2 * 0.000001016  # lbf/ft (approximate)
            
            # Critical velocity equation (Turner, 1969):
            # v_critical = C * sqrt((rho_l - rho_g) / rho_g) where C depends on sigma and wellbore conditions
            
            # Approximate constant C for vertical wells (from Turner)
            # C = 5.0 ft/s for typical conditions (critical velocity minimum)
            rho_g = wellhead_pressure_psi * gas_gravity / (10.73 * (temperature_f + 459.67) * 0.9)  # lb/ft³
            rho_l = oil_density_lbft3
            
            # Turner critical velocity (minimum)
            v_critical = 5.0 * math.sqrt((rho_l - rho_g) / rho_g)  # ft/s
            
            # Ensure minimum value
            v_critical = max(v_critical, 5.0)
            
            return round(v_critical, 3)
        except Exception:
            return 10.0

    def calculate_actual_gas_velocity(self, gas_rate_mmscfd, tubing_diameter_inch, wellhead_pressure_psi):
        """
        Calculate actual superficial gas velocity (ft/s)
        
        Parameters:
            gas_rate_mmscfd: Gas rate in MMscf/d
            tubing_diameter_inch: Tubing ID
            wellhead_pressure_psi: Average tubing pressure (psi)
        
        Returns:
            actual_velocity (ft/s)
        """
        try:
            # Cross-sectional area
            d_ft = tubing_diameter_inch / 12.0
            area_ft2 = math.pi * (d_ft ** 2) / 4.0
            
            # Actual gas rate at standard conditions
            gas_rate_scfd = gas_rate_mmscfd * 1e6  # scf/d
            
            # Actual volume at wellhead conditions (using Z=0.9)
            z = 0.9
            temp_rankine = self.temperature_f + 459.67
            actual_gas_rate_cuft_s = (gas_rate_scfd / 86400) * (10.73 * 0.9 * temp_rankine) / (wellhead_pressure_psi * self.gas_specific_gravity)
            
            # Superficial velocity
            velocity_ft_s = actual_gas_rate_cuft_s / area_ft2
            return max(velocity_ft_s, 0.0)
        except Exception:
            return 0.0