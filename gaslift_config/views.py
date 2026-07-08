"""
Dashboard view providing context data for the Gas Lift application.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.data_upload.models import DataUpload
from apps.analysis.models import AnalysisSession, WellTrendAnalysis


def dashboard(request):
    """Dashboard view with stats summary."""
    context = {}

    if request.user.is_authenticated:
        # Get total uploads for user
        total_uploads = DataUpload.objects.filter(user=request.user).count()

        # Get total analyses for user
        total_analyses = AnalysisSession.objects.filter(user=request.user).count()

        # Get total wells analyzed (from completed analyses)
        total_wells_analyzed = WellTrendAnalysis.objects.filter(
            analysis__user=request.user,
            analysis__status='completed'
        ).count()

        # Get top candidates (rank 1-10 from completed analyses)
        top_candidates = WellTrendAnalysis.objects.filter(
            analysis__user=request.user,
            analysis__status='completed',
            rank__gte=1,
            rank__lte=10
        ).count()

        context.update({
            'total_uploads': total_uploads,
            'total_analyses': total_analyses,
            'total_wells_analyzed': total_wells_analyzed,
            'top_candidates': top_candidates,
        })

    return render(request, 'base/dashboard.html', context)