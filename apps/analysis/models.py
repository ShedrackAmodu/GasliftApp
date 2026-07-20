from django.db import models
from django.contrib.auth.models import User
from apps.data_upload.models import DataUpload
import uuid

class AnalysisSession(models.Model):
    """Model for analysis sessions"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analysis_sessions')
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE, related_name='analysis_sessions')
    name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Analysis {self.id} - {self.user.username}"

class AnalysisWeights(models.Model):
    """Model for analysis parameter weights"""
    analysis = models.OneToOneField(AnalysisSession, on_delete=models.CASCADE, related_name='weights')
    bsw_weight = models.FloatField(default=100)
    oil_rate_weight = models.FloatField(default=100)
    glr_weight = models.FloatField(default=100)
    tubing_pressure_weight = models.FloatField(default=50)
    economic_limit_oil_bopd = models.FloatField(default=50, help_text="Economic oil rate limit (bopd)")
    gas_constraint_mmscf = models.FloatField(null=True, blank=True, help_text="Available lift gas (MMscf/d) for knapsack optimization")
    base_choke_size = models.CharField(max_length=20, blank=True, help_text="Base choke size for normalization")
    outlier_method = models.CharField(max_length=20, default='iqr', help_text="Outlier detection method")
    outlier_threshold = models.FloatField(default=1.5, help_text="Outlier detection threshold")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Weights for {self.analysis.id}"

class PVTProperties(models.Model):
    """Model for PVT fluid properties"""
    analysis = models.OneToOneField(AnalysisSession, on_delete=models.CASCADE, related_name='pvt_properties')
    api_gravity = models.FloatField(default=35.0, help_text="API gravity of produced oil")
    gas_specific_gravity = models.FloatField(default=0.65, help_text="Gas specific gravity (air=1.0)")
    water_salinity = models.FloatField(default=20000.0, help_text="Water salinity (ppm)")
    temperature = models.FloatField(default=180.0, help_text="Reservoir temperature (°F)")
    tubing_diameter = models.FloatField(default=2.875, help_text="Tubing inside diameter (inches)")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"PVT for {self.analysis.id}"

class CompletionData(models.Model):
    """Model for well completion data"""
    analysis = models.ForeignKey(AnalysisSession, on_delete=models.CASCADE, related_name='completion_data')
    well_id = models.CharField(max_length=255)
    mandrel_depths = models.JSONField(default=list, help_text="List of mandrel depths (ft)")
    packer_depth = models.FloatField(null=True, blank=True, help_text="Packer depth (ft)")
    tubing_od = models.FloatField(null=True, blank=True, help_text="Tubing outside diameter (inch)")
    tubing_id = models.FloatField(null=True, blank=True, help_text="Tubing inside diameter (inch)")
    injection_pressure_required = models.FloatField(null=True, blank=True, help_text="Min surface pressure to reach mandrel (psi)")
    feasibility_flag = models.CharField(max_length=50, default='unknown', choices=[
        ('feasible', 'Feasible'),
        ('requires_deepening', 'Requires Tubing Deepening'),
        ('pressure_limited', 'Insufficient Injection Pressure'),
        ('unknown', 'Unknown'),
    ])
    
    def __str__(self):
        return f"Completion data for {self.well_id}"

class WellTrendAnalysis(models.Model):
    """Model for individual well trend analysis"""
    TREND_CHOICES = [
        ('increasing', 'Increasing'),
        ('decreasing', 'Decreasing'),
        ('no_trend', 'No Trend'),
    ]
    
    MAGNITUDE_CHOICES = [
        ('slightly', 'Slightly'),
        ('moderately', 'Moderately'),
        ('aggressively', 'Aggressively'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis = models.ForeignKey(AnalysisSession, on_delete=models.CASCADE, related_name='well_trends')
    well_id = models.CharField(max_length=255)
    
    # Data quality and normalization flags
    is_choke_normalized = models.BooleanField(default=False)
    data_quality_score = models.FloatField(default=100.0, help_text="Percentage of valid data points")
    outlier_count = models.IntegerField(default=0, help_text="Number of outlier points removed")
    
    # BSW trends
    bsw_trend = models.CharField(max_length=20, choices=TREND_CHOICES, null=True, blank=True)
    bsw_slope = models.FloatField(null=True, blank=True)  # Sen's slope
    bsw_magnitude = models.CharField(max_length=20, choices=MAGNITUDE_CHOICES, null=True, blank=True)
    
    # Oil Rate trends
    oil_rate_trend = models.CharField(max_length=20, choices=TREND_CHOICES, null=True, blank=True)
    oil_rate_slope = models.FloatField(null=True, blank=True)
    oil_rate_magnitude = models.CharField(max_length=20, choices=MAGNITUDE_CHOICES, null=True, blank=True)
    
    # GLR trends
    glr_trend = models.CharField(max_length=20, choices=TREND_CHOICES, null=True, blank=True)
    glr_slope = models.FloatField(null=True, blank=True)
    glr_magnitude = models.CharField(max_length=20, choices=MAGNITUDE_CHOICES, null=True, blank=True)
    
    # Tubing Pressure trends
    tubing_pressure_trend = models.CharField(max_length=20, choices=TREND_CHOICES, null=True, blank=True)
    tubing_pressure_slope = models.FloatField(null=True, blank=True)
    tubing_pressure_magnitude = models.CharField(max_length=20, choices=MAGNITUDE_CHOICES, null=True, blank=True)
    
    # Flags for display
    bsw_flag = models.BooleanField(default=False)  # True if trend is negative (bad)
    oil_rate_flag = models.BooleanField(default=False)
    glr_flag = models.BooleanField(default=False)
    
    # Additional well metadata from upload
    prod_method = models.CharField(max_length=255, blank=True, default='')
    test_status = models.CharField(max_length=255, blank=True, default='')
    flow_line_pressure = models.FloatField(null=True, blank=True)
    well_choke_size = models.CharField(max_length=50, blank=True, default='')
    
    # Choke normalization data (for charts)
    original_values = models.JSONField(default=dict, blank=True, help_text="Original pre-normalization values")
    corrected_values = models.JSONField(default=dict, blank=True, help_text="Corrected values after normalization")
    rejected_indices = models.JSONField(default=list, blank=True, help_text="Indices of rejected outlier points")
    
    # Reservoir and IPR data
    static_reservoir_pressure = models.FloatField(null=True, blank=True, help_text="Static reservoir pressure (psi)")
    flowing_bhp = models.FloatField(null=True, blank=True, help_text="Flowing bottom-hole pressure (psi)")
    productivity_index = models.FloatField(null=True, blank=True, help_text="Productivity Index (bopd/psi)")
    pi_trend = models.CharField(max_length=20, choices=TREND_CHOICES, null=True, blank=True)
    pi_slope = models.FloatField(null=True, blank=True)
    
    # Liquid loading diagnostics
    liquid_loading_flag = models.BooleanField(default=False, help_text="True if well is liquid-loaded")
    critical_glr = models.FloatField(null=True, blank=True, help_text="Critical GLR for liquid loading (scf/bbl)")
    actual_glr = models.FloatField(null=True, blank=True, help_text="Actual average GLR (scf/bbl)")
    critical_velocity = models.FloatField(null=True, blank=True, help_text="Critical gas velocity (ft/s)")
    actual_velocity = models.FloatField(null=True, blank=True, help_text="Actual gas velocity (ft/s)")
    
    # Economic forecasting
    days_to_economic_limit = models.IntegerField(null=True, blank=True, help_text="Days until economic limit reached")
    projected_oil_rate_6mo = models.FloatField(null=True, blank=True, help_text="Projected oil rate in 6 months (bopd)")
    
    # Gas allocation
    recommended_gas_mmscf = models.FloatField(null=True, blank=True, help_text="Recommended gas injection (MMscf/d)")
    gas_utilization_efficiency = models.FloatField(null=True, blank=True, help_text="Gas utilization efficiency (0-100)")
    
    # Feasibility
    completion_feasibility = models.CharField(max_length=50, choices=[
        ('feasible', 'Feasible'),
        ('requires_deepening', 'Requires Tubing Deepening'),
        ('pressure_limited', 'Insufficient Injection Pressure'),
        ('unknown', 'Unknown'),
    ], default='unknown')
    
    candidate_score = models.FloatField(default=0)
    rank = models.IntegerField(null=True, blank=True)
    summary_comment = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-candidate_score']
    
    def __str__(self):
        return f"{self.well_id} - Analysis {self.analysis.id}"
