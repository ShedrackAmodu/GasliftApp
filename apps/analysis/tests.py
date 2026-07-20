from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from apps.analysis.models import AnalysisSession, AnalysisWeights
from apps.data_upload.models import ColumnMapping, DataUpload


class AnalysisWorkflowTests(TestCase):
    @override_settings(
        ALLOWED_HOSTS=['localhost', '127.0.0.1', 'testserver'],
        STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
    )
    def test_full_analysis_and_export_workflow(self):
        User = get_user_model()
        user = User.objects.create_user(username='workflow-user', password='secret123')

        csv_path = Path('media/uploads/2026/07/13/sample_well_data.csv')
        csv_bytes = csv_path.read_bytes()
        upload = DataUpload.objects.create(
            user=user,
            file=SimpleUploadedFile(csv_path.name, csv_bytes, content_type='text/csv'),
            filename=csv_path.name,
            file_format='csv',
            file_size=len(csv_bytes),
            total_rows=0,
            columns=[],
        )

        ColumnMapping.objects.create(
            upload=upload,
            mapping={
                'Well': 'Well',
                'Date': 'Date',
                'BS&W (%)': 'BS&W (%)',
                'Net Oil (bopd)': 'Net Oil (bopd)',
                'Form.GLR (scf/bbl)': 'Form.GLR (scf/bbl)',
                'Prod Method': 'Prod Method',
                'Test Status': 'Test Status',
                'Tubing Pressure (psi)': 'Tubing Pressure (psi)',
                'Flow Line Pressure (psi)': 'Flow Line Pressure (psi)',
                'Well Choke Size': 'Well Choke Size',
            },
            is_valid=True,
        )

        analysis = AnalysisSession.objects.create(upload=upload, user=user, status='pending')
        AnalysisWeights.objects.get_or_create(analysis=analysis)

        client = Client()
        client.force_login(user)

        response = client.post(
            f'/api/analysis/{analysis.id}/run/',
            {'base_choke_size': '24/64', 'outlier_method': 'iqr', 'outlier_threshold': '1.5'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        analysis.refresh_from_db()
        self.assertEqual(analysis.status, 'completed')
        self.assertIsNone(analysis.error_message)
        self.assertGreater(analysis.well_trends.count(), 0)

        excel_response = client.get(f'/api/results/{analysis.id}/export-excel/')
        self.assertEqual(excel_response.status_code, 200)
        self.assertIn('spreadsheetml', excel_response['Content-Type'])

        csv_response = client.get(f'/api/results/{analysis.id}/export-csv/')
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn('text/csv', csv_response['Content-Type'])
