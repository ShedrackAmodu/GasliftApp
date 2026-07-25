"""
Dashboard view providing context data for the Gas Lift application.
"""
from django.http import HttpResponse
from django.shortcuts import render
from apps.data_upload.models import DataUpload
from apps.analysis.models import AnalysisSession, WellTrendAnalysis


def download_manual_pdf(request):
    """Render the user manual as a PDF response for download or inline preview."""
    from django.template.loader import render_to_string
    from weasyprint import HTML

    template = 'base/user_manual_print.html'
    html_string = render_to_string(template, request=request)
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()

    content_disposition = 'attachment; filename="Gas_Lift_User_Manual.pdf"'
    if request.GET.get('inline') == '1':
        content_disposition = 'inline; filename="Gas_Lift_User_Manual.pdf"'

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = content_disposition
    return response


def dashboard(request):
    """Dashboard view with stats summary."""
    context = {}

    if request.user.is_authenticated:
        total_uploads = DataUpload.objects.filter(user=request.user).count()
        total_analyses = AnalysisSession.objects.filter(user=request.user).count()
        total_wells_analyzed = WellTrendAnalysis.objects.filter(
            analysis__user=request.user,
            analysis__status='completed'
        ).count()
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


def user_manual_print(request):
    """Render a print-optimized version of the user manual.
    The browser's print dialog will open automatically, allowing the user
    to save as PDF using the browser's built-in 'Save as PDF' feature."""
    return render(request, 'base/user_manual_print.html')
