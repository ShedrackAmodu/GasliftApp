import os
import json
import django
from pathlib import Path
from django.test import Client
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaslift_config.settings')
django.setup()

User = get_user_model()
user, created = User.objects.get_or_create(username='uiuser', defaults={'email': 'ui@example.com'})
user.set_password('pass123')
user.save()

client = Client()
assert client.login(username='uiuser', password='pass123')

p = Path('test_data/well_data2.csv')
with p.open('rb') as fh:
    response = client.post('/api/upload/upload/', {'file': fh}, follow=True)
print('upload', response.status_code, response.redirect_chain)

upload = None
from apps.data_upload.models import DataUpload
upload = DataUpload.objects.filter(user=user).order_by('-upload_date').first()
print('upload model', bool(upload), upload.id if upload else None)

mapping = {
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
}
response = client.post(f'/api/upload/{upload.id}/mapping/', {'mapping': json.dumps(mapping)}, follow=True)
print('mapping', response.status_code, response.redirect_chain)
response = client.get(f'/api/upload/{upload.id}/preview/', follow=True)
print('preview', response.status_code)
response = client.post(f'/api/analysis/{upload.id}/weights/', {
    'bsw_weight': '100',
    'oil_rate_weight': '100',
    'glr_weight': '100',
    'tubing_pressure_weight': '50',
    'economic_limit_oil_bopd': '50',
    'gas_constraint_mmscf': '',
    'base_choke_size': '24/64',
    'outlier_method': 'iqr',
    'outlier_threshold': '1.5',
}, follow=True)
print('weights', response.status_code, response.redirect_chain)
from apps.analysis.models import AnalysisSession
analysis = AnalysisSession.objects.filter(upload=upload).order_by('-created_at').first()
print('analysis', bool(analysis), analysis.id if analysis else None)
response = client.get(f'/api/analysis/{analysis.id}/trends/', follow=True)
print('trends', response.status_code)
response = client.post(f'/api/analysis/{analysis.id}/run/', {'selected_wells': json.dumps(['WELL-001'])}, follow=True, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
print('run', response.status_code, response.json())
print('analysis status', analysis.status, analysis.error_message)
