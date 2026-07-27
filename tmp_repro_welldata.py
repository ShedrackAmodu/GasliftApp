import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaslift_config.settings')
import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.analysis.models import AnalysisSession

user = get_user_model().objects.filter(is_active=True).first()
print('user:', user)
aid = '8a3509e6-d44a-46e6-b282-c09e5eb0e3dc'
try:
    analysis = AnalysisSession.objects.get(id=aid)
    print('analysis owner:', analysis.user, 'upload:', analysis.upload)
except Exception as e:
    print('analysis missing:', e)

client = Client()
if user:
    client.force_login(user)
url = f'/api/analysis/{aid}/well-data/WELL-ALL_FLAGS/'
print('requesting', url)
response = client.get(url)
print('status:', response.status_code)
print('content:', response.content)
print('headers:', response.items())
