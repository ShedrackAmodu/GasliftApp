from django.urls import path
from . import views

app_name = 'results'

urlpatterns = [
    path('<uuid:analysis_id>/view/', views.view_results, name='view_results'),
    path('<uuid:analysis_id>/export-excel/', views.export_excel, name='export_excel'),
    path('<uuid:analysis_id>/export-csv/', views.export_csv, name='export_csv'),
    path('<uuid:analysis_id>/export-pdf/', views.export_pdf, name='export_pdf'),
    path('<uuid:analysis_id>/filter/', views.filter_results, name='filter_results'),
]
