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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Weights for {self.analysis.id}"

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
    
    candidate_score = models.FloatField(default=0)
    rank = models.IntegerField(null=True, blank=True)
    summary_comment = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-candidate_score']
    
    def __str__(self):
        return f"{self.well_id} - Analysis {self.analysis.id}"