"""
Completion feasibility calculations for gas lift wells.
"""
import math

class CompletionFeasibilityChecker:
    """Check if gas lift injection is feasible given completion hardware"""
    
    # Typical values (can be overridden)
    GAS_GRADIENT_PSI_PER_FT = 0.05  # ~0.05 psi/ft for gas column
    LIQUID_GRADIENT_PSI_PER_FT = 0.465  # ~0.465 psi/ft for water/oil
    FRICTION_LOSS_PSI = 50  # Approximate friction loss
    WELLHEAD_PRESSURE_PSI = 100  # Minimum wellhead pressure
    
    @staticmethod
    def calculate_injection_pressure_requirement(mandrel_depth_ft, packer_depth_ft=None,
                                                  tubing_id_inch=None, fluid_gradient_psi_per_ft=None,
                                                  gas_gradient_psi_per_ft=None):
        """
        Calculate minimum surface injection pressure to reach mandrel depth.
        
        Parameters:
            mandrel_depth_ft: Depth to injection point (ft)
            packer_depth_ft: Packer depth (ft), defaults to mandrel depth
            tubing_id_inch: Tubing inside diameter (inch)
            fluid_gradient_psi_per_ft: Pressure gradient (psi/ft)
            gas_gradient_psi_per_ft: Gas gradient (psi/ft)
        
        Returns:
            Required injection pressure (psi)
        """
        try:
            if fluid_gradient_psi_per_ft is None:
                fluid_gradient_psi_per_ft = CompletionFeasibilityChecker.LIQUID_GRADIENT_PSI_PER_FT
            if gas_gradient_psi_per_ft is None:
                gas_gradient_psi_per_ft = CompletionFeasibilityChecker.GAS_GRADIENT_PSI_PER_FT
            if packer_depth_ft is None:
                packer_depth_ft = mandrel_depth_ft
            
            # Simplified: assume gas lift gas fills above packer, liquid below
            # Pressure at mandrel = hydrostatic of gas column + hydrostatic of liquid column
            if packer_depth_ft > 0:
                gas_column = packer_depth_ft * gas_gradient_psi_per_ft
            else:
                gas_column = 0
            
            liquid_column = max(0, mandrel_depth_ft - packer_depth_ft) * fluid_gradient_psi_per_ft
            
            # Add friction and wellhead pressure
            total_pressure = gas_column + liquid_column + CompletionFeasibilityChecker.FRICTION_LOSS_PSI + CompletionFeasibilityChecker.WELLHEAD_PRESSURE_PSI
            
            return round(total_pressure, 2)
        except Exception:
            return None
    
    @staticmethod
    def check_feasibility(required_pressure_psi, available_compression_pressure_psi):
        """
        Determine if injection is feasible given compression capability.
        
        Returns:
            ('feasible', None) if pressure sufficient
            ('pressure_limited', deficit_psi) if insufficient
            ('requires_deepening', None) if mandrel too deep
        """
        try:
            if required_pressure_psi is None or available_compression_pressure_psi is None:
                return 'unknown', None
            
            deficit = required_pressure_psi - available_compression_pressure_psi
            
            if deficit <= 0:
                return 'feasible', None
            elif deficit < 200:  # Within 200 psi, might be salvageable
                return 'pressure_limited', deficit
            else:
                return 'requires_deepening', deficit
        except Exception:
            return 'unknown', None
    
    @staticmethod
    def analyze_completion(mandrel_depths, packer_depth_ft, tubing_id_inch,
                           available_compression_pressure_psi, fluid_gradient_psi_per_ft=None):
        """
        Full completion feasibility analysis.
        
        Parameters:
            mandrel_depths: List of mandrel depths (ft), deepest first typically
            packer_depth_ft: Packer depth (ft)
            tubing_id_inch: Tubing inside diameter (inch)
            available_compression_pressure_psi: Max surface injection pressure (psi)
            fluid_gradient_psi_per_ft: Override gradient
        
        Returns:
            dict with feasibility results per mandrel and overall recommendation
        """
        results = {
            'mandrel_analysis': [],
            'overall_feasible': False,
            'deepest_feasible_mandrel': None,
            'required_pressure_at_deepest': None,
            'recommendation': ''
        }
        
        try:
            if not mandrel_depths:
                return results
            
            # Sort depths ascending (shallow to deep)
            sorted_depths = sorted([d for d in mandrel_depths if d is not None])
            
            for depth in sorted_depths:
                req_pressure = CompletionFeasibilityChecker.calculate_injection_pressure_requirement(
                    depth, packer_depth_ft, tubing_id_inch, fluid_gradient_psi_per_ft
                )
                feasibility, deficit = CompletionFeasibilityChecker.check_feasibility(
                    req_pressure, available_compression_pressure_psi
                )
                
                results['mandrel_analysis'].append({
                    'depth_ft': depth,
                    'required_pressure_psi': req_pressure,
                    'feasibility': feasibility,
                    'deficit_psi': deficit,
                    'available_compression_psi': available_compression_pressure_psi
                })
                
                if feasibility == 'feasible':
                    results['deepest_feasible_mandrel'] = depth
                    results['required_pressure_at_deepest'] = req_pressure
            
            # Determine overall feasibility
            if results['deepest_feasible_mandrel']:
                results['overall_feasible'] = True
                results['recommendation'] = (
                    f"Feasible to deepest mandrel at {results['deepest_feasible_mandrel']} ft. "
                    f"Required pressure: {results['required_pressure_at_deepest']} psi."
                )
            else:
                # Find shallowest mandrel
                shallowest = sorted_depths[0] if sorted_depths else None
                if shallowest:
                    req_pressure = CompletionFeasibilityChecker.calculate_injection_pressure_requirement(
                        shallowest, packer_depth_ft, tubing_id_inch, fluid_gradient_psi_per_ft
                    )
                    feasibility, deficit = CompletionFeasibilityChecker.check_feasibility(
                        req_pressure, available_compression_pressure_psi
                    )
                    if feasibility == 'pressure_limited':
                        results['recommendation'] = (
                            f"Pressure limited. Need {req_pressure} psi but only have {available_compression_pressure_psi} psi. "
                            f"Consider adding compression or reducing mandral depth."
                        )
                    else:
                        results['recommendation'] = "Requires tubing deepening to reach mandrels."
                else:
                    results['recommendation'] = "No valid mandrel depths provided."
            
            return results
        except Exception:
            return results