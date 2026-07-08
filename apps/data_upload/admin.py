from django.contrib import admin
from .models import DataUpload, ColumnMapping, PreviewData

@admin.register(DataUpload)
class DataUploadAdmin(admin.ModelAdmin):
    list_display = ('filename', 'user', 'file_format', 'upload_date', 'is_processed')
    search_fields = ('filename', 'user__username')
    list_filter = ('file_format', 'upload_date', 'is_processed')

@admin.register(ColumnMapping)
class ColumnMappingAdmin(admin.ModelAdmin):
    list_display = ('upload', 'is_valid', 'created_at')
    search_fields = ('upload__filename',)

@admin.register(PreviewData)
class PreviewDataAdmin(admin.ModelAdmin):
    list_display = ('upload', 'created_at')
    search_fields = ('upload__filename',)
