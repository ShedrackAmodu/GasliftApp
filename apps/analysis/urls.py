from django.urls import path
from . import views

app_name = 'analysis'

urlpatterns = [
    path('<uuid:upload_id>/weights/', views.adjust_weights, name='adjust_weights'),
    path('<uuid:analysis_id>/trends/', views.well_trends, name='well_trends'),
    path('<uuid:analysis_id>/well-data/<str:well_name>/', views.get_well_data, name='get_well_data'),
    path('<uuid:analysis_id>/run/', views.run_analysis, name='run_analysis'),
    path('<uuid:analysis_id>/delete/', views.delete_analysis, name='delete_analysis'),
    path('my-analyses/', views.my_analyses, name='my_analyses'),
]
