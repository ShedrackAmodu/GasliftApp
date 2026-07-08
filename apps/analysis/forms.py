from django import forms
from .models import AnalysisSession, AnalysisWeights

class AnalysisWeightsForm(forms.ModelForm):
    """Form for adjusting analysis weights"""
    class Meta:
        model = AnalysisWeights
        fields = ['bsw_weight', 'oil_rate_weight', 'glr_weight', 'tubing_pressure_weight']
        widgets = {
            'bsw_weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 200}),
            'oil_rate_weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 200}),
            'glr_weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 200}),
            'tubing_pressure_weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 200}),
        }

class AnalysisSessionForm(forms.ModelForm):
    """Form for creating analysis session"""
    class Meta:
        model = AnalysisSession
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Analysis Name (optional)'}),
        }
