from django.contrib import admin
from .models import AnalysisSession, AnalysisWeights, WellTrendAnalysis

@admin.register(AnalysisSession)
class AnalysisSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'upload', 'status', 'created_at', 'completed_at')
    search_fields = ('user__username', 'upload__filename')
    list_filter = ('status', 'created_at')

@admin.register(AnalysisWeights)
class AnalysisWeightsAdmin(admin.ModelAdmin):
    list_display = ('analysis', 'bsw_weight', 'oil_rate_weight', 'glr_weight', 'tubing_pressure_weight')

@admin.register(WellTrendAnalysis)
class WellTrendAnalysisAdmin(admin.ModelAdmin):
    list_display = ('well_id', 'analysis', 'rank', 'candidate_score', 'bsw_flag', 'oil_rate_flag', 'glr_flag')
    search_fields = ('well_id', 'analysis__id')
    list_filter = ('analysis', 'bsw_flag', 'oil_rate_flag', 'glr_flag')
