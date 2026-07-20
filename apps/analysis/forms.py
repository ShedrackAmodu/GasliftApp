from django import forms
from .models import AnalysisSession, AnalysisWeights, PVTProperties

class AnalysisWeightsForm(forms.ModelForm):
    """Form for adjusting analysis weights and economic settings"""
    base_choke_size = forms.CharField(
        max_length=20,
        required=False,
        help_text="Base choke size for normalization (e.g., 24/64\")",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 24/64"'}),
    )
    
    outlier_method = forms.ChoiceField(
        choices=[('iqr', 'IQR (1.5x)'), ('hampel', 'Hampel Filter')],
        initial='iqr',
        required=False,
        help_text="Outlier detection method",
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    outlier_threshold = forms.FloatField(
        initial=1.5,
        min_value=1.0,
        max_value=3.0,
        required=False,
        help_text="Threshold multiplier for outlier detection",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
    )
    
    class Meta:
        model = AnalysisWeights
        fields = [
            'bsw_weight', 'oil_rate_weight', 'glr_weight', 'tubing_pressure_weight',
            'economic_limit_oil_bopd', 'gas_constraint_mmscf', 'base_choke_size',
            'outlier_method', 'outlier_threshold',
        ]
        widgets = {
            'bsw_weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 200}),
            'oil_rate_weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 200}),
            'glr_weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 200}),
            'tubing_pressure_weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 200}),
            'economic_limit_oil_bopd': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'gas_constraint_mmscf': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '0.1', 'placeholder': 'e.g., 10'}),
        }

class AnalysisSessionForm(forms.ModelForm):
    """Form for creating analysis session"""
    class Meta:
        model = AnalysisSession
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Analysis Name (optional)'}),
        }

class PVTPropertiesForm(forms.ModelForm):
    """Form for setting PVT fluid properties"""
    class Meta:
        model = PVTProperties
        fields = ['api_gravity', 'gas_specific_gravity', 'water_salinity', 'temperature', 'tubing_diameter']
        widgets = {
            'api_gravity': forms.NumberInput(attrs={'class': 'form-control', 'min': 10, 'max': 60, 'step': '0.1', 'placeholder': 'e.g., 35'}),
            'gas_specific_gravity': forms.NumberInput(attrs={'class': 'form-control', 'min': 0.5, 'max': 1.5, 'step': '0.01', 'placeholder': 'e.g., 0.65'}),
            'water_salinity': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '1000', 'placeholder': 'e.g., 20000'}),
            'temperature': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '5', 'placeholder': 'e.g., 180'}),
            'tubing_diameter': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10, 'step': '0.001', 'placeholder': 'e.g., 2.875'}),
        }

class CompletionDataForm(forms.Form):
    """Form for uploading completion data"""
    well_id = forms.CharField(
        max_length=255,
        help_text="Well name (must match production data)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., WELL-001'}),
    )
    mandrel_depths = forms.CharField(
        help_text="Comma-separated mandrel depths in feet (e.g., 3000, 4000, 5000)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 3000, 4000, 5000'}),
    )
    packer_depth = forms.FloatField(
        min_value=0,
        help_text="Packer depth (ft)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 3500'}),
    )
    tubing_od = forms.FloatField(
        min_value=0,
        required=False,
        help_text="Tubing outside diameter (inch)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2.875'}),
    )
    tubing_id = forms.FloatField(
        min_value=0,
        required=False,
        help_text="Tubing inside diameter (inch)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2.441'}),
    )
    available_compression_pressure = forms.FloatField(
        min_value=0,
        help_text="Maximum surface injection pressure available (psi)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2500'}),
    )
    
    def clean_mandrel_depths(self):
        """Parse comma-separated mandrel depths"""
        depths_str = self.cleaned_data['mandrel_depths']
        depths = []
        for part in depths_str.split(','):
            part = part.strip()
            if part:
                try:
                    depths.append(float(part))
                except ValueError:
                    raise forms.ValidationError(f"Invalid depth value: {part}")
        return depths
