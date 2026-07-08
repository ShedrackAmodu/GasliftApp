from django import forms
from .models import DataUpload, ColumnMapping

class FileUploadForm(forms.ModelForm):
    """File upload form"""
    class Meta:
        model = DataUpload
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.xlsx, .csv'
            })
        }

    def clean_file(self):
        uploaded_file = self.cleaned_data.get('file')
        if uploaded_file:
            allowed_extensions = ['xlsx', 'csv']
            extension = uploaded_file.name.split('.')[-1].lower()
            if extension not in allowed_extensions:
                raise forms.ValidationError('Only .xlsx and .csv files are supported.')
            max_size = 100 * 1024 * 1024  # 100 MB
            if uploaded_file.size > max_size:
                raise forms.ValidationError('File size exceeds the 100 MB limit.')
        return uploaded_file

class ColumnMappingForm(forms.ModelForm):
    """Column mapping form"""
    class Meta:
        model = ColumnMapping
        fields = ['mapping']
        widgets = {
            'mapping': forms.HiddenInput()
        }
