from django.db import models
from django.contrib.auth.models import User
import uuid

class DataUpload(models.Model):
    """Model for uploaded well test data"""
    FILE_FORMAT_CHOICES = [
        ('xlsx', 'Excel (.xlsx)'),
        ('csv', 'CSV (.csv)'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploads')
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_format = models.CharField(max_length=10, choices=FILE_FORMAT_CHOICES)
    file_size = models.IntegerField()  # Size in bytes
    total_rows = models.IntegerField(default=0)
    columns = models.JSONField(default=list)  # List of column names
    upload_date = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    is_processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-upload_date']
    
    def __str__(self):
        return f"{self.filename} - {self.user.username}"

class ColumnMapping(models.Model):
    """Model for column mappings"""
    REQUIRED_FIELDS = [
        'Well',
        'Date',
        'BS&W (%)',
        'Net Oil (bopd)',
        'Form.GLR (scf/bbl)',
        'Prod Method',
        'Test Status',
        'Tubing Pressure (psi)',
        'Flow Line Pressure (psi)',
        'Well Choke Size',
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.OneToOneField(DataUpload, on_delete=models.CASCADE, related_name='column_mapping')
    mapping = models.JSONField()  # Dict of required field -> file column mapping
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_valid = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Mapping for {self.upload.filename}"

class PreviewData(models.Model):
    """Model for preview/sample data"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.OneToOneField(DataUpload, on_delete=models.CASCADE, related_name='preview')
    sample_data = models.JSONField()  # First 50 rows of processed data
    data_quality_report = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Preview for {self.upload.filename}"
