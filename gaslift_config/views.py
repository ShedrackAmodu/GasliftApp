"""
Dashboard view providing context data for the Gas Lift application.
"""
from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test.utils import override_settings
from django.conf import settings
from apps.data_upload.models import DataUpload
from apps.analysis.models import AnalysisSession, WellTrendAnalysis


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


def download_manual_pdf(request):
    """Generate and download a PDF of the user manual."""
    try:
        from weasyprint import HTML

        with override_settings(
            STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage'
        ):
            html_string = render_to_string('base/user_manual.html', {'request': request})

        try:
            base_url = request.build_absolute_uri('/')
        except Exception:
            scheme = request.META.get('wsgi.url_scheme', 'http')
            host = request.META.get('HTTP_HOST', 'localhost')
            base_url = f'{scheme}://{host}/'

        pdf_file = HTML(string=html_string, base_url=base_url).write_pdf()

        response = HttpResponse(pdf_file, content_type='application/pdf')
        disposition = 'inline; filename="Gas_Lift_User_Manual.pdf"' if request.GET.get('inline') == '1' else 'attachment; filename="Gas_Lift_User_Manual.pdf"'
        response['Content-Disposition'] = disposition
        response['Content-Length'] = len(pdf_file)
        return response
    except Exception as e:
        if hasattr(request, '_messages'):
            from django.contrib import messages
            messages.error(
                request,
                f'Could not generate PDF: {str(e)}. You can view the manual online or print it from your browser.'
            )

        with override_settings(
            STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage'
        ):
            return render(request, 'base/user_manual.html', {'pdf_error': str(e)})