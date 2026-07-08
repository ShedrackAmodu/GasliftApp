from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
import json

from .models import DataUpload, ColumnMapping, PreviewData
from .forms import FileUploadForm, ColumnMappingForm
from .utils import DataProcessor

@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def upload_file(request):
    """File upload view - Step 1"""
    MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
    
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            
            # Validate file size
            if uploaded_file.size > MAX_UPLOAD_SIZE:
                return render(request, 'data_upload/upload.html', {
                    'form': form,
                    'error': f'File size exceeds the 100 MB limit. Your file is {uploaded_file.size / (1024*1024):.1f} MB.'
                })
            
            upload = form.save(commit=False)
            upload.user = request.user
            upload.filename = uploaded_file.name
            upload.file_format = uploaded_file.name.split('.')[-1].lower()
            upload.file_size = uploaded_file.size
            
            # Validate file format
            if upload.file_format not in ['xlsx', 'csv']:
                return render(request, 'data_upload/upload.html', {
                    'form': form,
                    'error': 'Unsupported file format. Please upload .xlsx or .csv files only.'
                })
            
            upload.save()
            
            return redirect('data_upload:column_mapping', upload_id=upload.id)
    else:
        form = FileUploadForm()
    
    return render(request, 'data_upload/upload.html', {'form': form})

@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def column_mapping(request, upload_id):
    """Column mapping view - Step 2"""
    upload = get_object_or_404(DataUpload, id=upload_id, user=request.user)
    
    if request.method == 'POST':
        mapping_data = request.POST.get('mapping')
        mapping = json.loads(mapping_data)
        
        # Validate mapping
        if not DataProcessor.validate_mapping(mapping):
            return render(request, 'data_upload/column_mapping.html', {
                'upload': upload,
                'available_columns': upload.columns,
                'error': 'All required fields must be mapped'
            })
        
        # Create or update column mapping
        col_map, created = ColumnMapping.objects.update_or_create(
            upload=upload,
            defaults={'mapping': mapping, 'is_valid': True}
        )
        
        # Invalidate existing preview when mapping changes (force re-processing)
        PreviewData.objects.filter(upload=upload).delete()
        
        messages.success(request, 'Columns mapped successfully.')
        return redirect('data_upload:preview_data', upload_id=upload.id)
    
    # Try to read columns from uploaded file
    try:
        rows = DataProcessor.read_file(upload.file, upload.file_format)
        available_columns = DataProcessor.detect_columns(rows)
        upload.columns = available_columns
        upload.total_rows = len(rows)
        upload.save()
    except Exception as e:
        upload.error_message = str(e)
        upload.save()
        available_columns = []
    
    # Get existing mapping if any
    try:
        col_mapping = ColumnMapping.objects.get(upload=upload)
        current_mapping = col_mapping.mapping
    except ColumnMapping.DoesNotExist:
        current_mapping = {}
    
    auto_mapping = DataProcessor.auto_map_columns(available_columns)
    mapping_pairs = [
        (field, current_mapping.get(field, auto_mapping.get(field, '')))
        for field in ColumnMapping.REQUIRED_FIELDS
    ]
    
    context = {
        'upload': upload,
        'available_columns': available_columns,
        'current_mapping': current_mapping,
        'mapping_pairs': mapping_pairs,
        'auto_mapping': auto_mapping,
    }
    
    return render(request, 'data_upload/column_mapping.html', context)

@login_required(login_url='accounts:login')
@require_http_methods(["GET"])
def preview_data(request, upload_id):
    """Data preview view - Step 3"""
    upload = get_object_or_404(DataUpload, id=upload_id, user=request.user)
    
    try:
        col_mapping = ColumnMapping.objects.get(upload=upload)
    except ColumnMapping.DoesNotExist:
        return redirect('data_upload:column_mapping', upload_id=upload.id)
    
    # Create or get preview
    try:
        preview = PreviewData.objects.get(upload=upload)
    except PreviewData.DoesNotExist:
        preview, error = DataProcessor.create_preview(upload, col_mapping.mapping)
        if error:
            return render(request, 'data_upload/preview.html', {
                'upload': upload,
                'error': error
            })
    
    context = {
        'upload': upload,
        'preview': preview,
        'sample_data': preview.sample_data[:20] if preview else [],
        'quality_report': preview.data_quality_report if preview else {}
    }
    
    return render(request, 'data_upload/preview.html', context)

@login_required(login_url='accounts:login')
@require_http_methods(["GET"])
def my_uploads(request):
    """List user's uploads"""
    uploads = DataUpload.objects.filter(user=request.user)
    return render(request, 'data_upload/my_uploads.html', {'uploads': uploads})

@login_required(login_url='accounts:login')
@require_POST
def delete_upload(request, upload_id):
    """Delete an upload and associated data"""
    upload = get_object_or_404(DataUpload, id=upload_id, user=request.user)
    # Get the file path before deleting the record
    file_path = upload.file.path if upload.file else None
    upload_id_str = str(upload.id)
    upload.delete()
    messages.success(request, f'Upload "{upload.filename}" deleted successfully.')
    return redirect('data_upload:my_uploads')
