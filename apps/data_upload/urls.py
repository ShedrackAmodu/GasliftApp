from django.urls import path
from . import views

app_name = 'data_upload'

urlpatterns = [
    path('upload/', views.upload_file, name='upload'),
    path('<uuid:upload_id>/mapping/', views.column_mapping, name='column_mapping'),
    path('<uuid:upload_id>/preview/', views.preview_data, name='preview_data'),
    path('<uuid:upload_id>/delete/', views.delete_upload, name='delete_upload'),
    path('my-uploads/', views.my_uploads, name='my_uploads'),
]
