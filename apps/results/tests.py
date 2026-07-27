from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.data_upload.models import DataUpload
from apps.analysis.models import AnalysisSession, WellTrendAnalysis


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class ResultsExportTests(TestCase):
    def test_export_endpoints_return_expected_types_and_scope(self):
        user = get_user_model().objects.create_user(username='exporter', password='secret123')

        upload = DataUpload.objects.create(
            user=user,
            file=SimpleUploadedFile('export.csv', b'Well,Date\nWELL-1,2024-01-01\n', content_type='text/csv'),
            filename='export.csv',
            file_format='csv',
            file_size=20,
            total_rows=1,
            columns=['Well', 'Date'],
        )

        # Analysis with two wells but selected_wells limits the scope
        analysis = AnalysisSession.objects.create(user=user, upload=upload, status='completed', selected_wells=['WELL-1'])

        WellTrendAnalysis.objects.create(analysis=analysis, well_id='WELL-1', candidate_score=10, rank=1)
        WellTrendAnalysis.objects.create(analysis=analysis, well_id='WELL-2', candidate_score=5, rank=2)

        self.client.force_login(user)

        # CSV export: ensure only selected well present in output
        resp_csv = self.client.get(reverse('results:export_csv', kwargs={'analysis_id': analysis.id}))
        self.assertEqual(resp_csv.status_code, 200)
        self.assertIn('text/csv', resp_csv['Content-Type'])
        content = resp_csv.content.decode('utf-8')
        self.assertIn('WELL-1', content)
        self.assertNotIn('WELL-2', content)

        # Excel export: returns spreadsheet bytes
        resp_xlsx = self.client.get(reverse('results:export_excel', kwargs={'analysis_id': analysis.id}))
        self.assertEqual(resp_xlsx.status_code, 200)
        self.assertIn('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', resp_xlsx['Content-Type'])

        # PDF export: may return PDF bytes or HTML fallback depending on environment
        resp_pdf = self.client.get(reverse('results:export_pdf', kwargs={'analysis_id': analysis.id}))
        self.assertEqual(resp_pdf.status_code, 200)
        # Accept either PDF or HTML bytes
        self.assertTrue('application/pdf' in resp_pdf['Content-Type'] or resp_pdf['Content-Type'].startswith('text/'))
