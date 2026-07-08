import pandas as pd
import logging
import re
from django.core.files.storage import default_storage
from .models import DataUpload, ColumnMapping, PreviewData

logger = logging.getLogger(__name__)

class DataProcessor:
    """Handles data processing and validation."""
    
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

    FIELD_ALIASES = {
        'Well': ['well', 'wellname', 'well_id', 'wellid', 'wellnameid', 'well name'],
        'Date': ['date', 'testdate', 'datetime', 'date_time', 'test_date'],
        'BS&W (%)': ['bsw', 'bs&w', 'watercut', 'wc', 'watercutpercent', 'watercut%'],
        'Net Oil (bopd)': ['netoil', 'oilrate', 'oil_bopd', 'oilratebopd', 'oilbopd'],
        'Form.GLR (scf/bbl)': ['glr', 'formglr', 'gasliquidratio', 'gasliquidratio_scf_bbl'],
        'Prod Method': ['prodmethod', 'productionmethod', 'production_method', 'method'],
        'Test Status': ['teststatus', 'status', 'test_status'],
        'Tubing Pressure (psi)': ['tubingpressure', 'thp', 'tp', 'tubingpressurepsi'],
        'Flow Line Pressure (psi)': ['flowlinepressure', 'flp', 'fp', 'flowlinepressurepsi'],
        'Well Choke Size': ['wellchokesize', 'chokesize', 'choke', 'wellchoke', 'choke size'],
    }
    
    @staticmethod
    def detect_columns(df):
        """Detect available columns in uploaded file"""
        return list(df.columns)

    @staticmethod
    def normalize_name(value):
        if value is None:
            return ''
        return re.sub(r'[^a-z0-9]+', '', str(value).lower())
    
    @classmethod
    def auto_map_columns(cls, available_columns):
        """Suggest likely column matches for the required fields."""
        mapping = {}
        available_columns = [col for col in available_columns if col is not None]

        for field in cls.REQUIRED_FIELDS:
            best_match = None
            best_score = 0
            aliases = cls.FIELD_ALIASES.get(field, [field])
            normalized_aliases = [cls.normalize_name(alias) for alias in aliases]

            for column in available_columns:
                normalized_column = cls.normalize_name(column)
                if not normalized_column:
                    continue

                score = 0
                if normalized_column in normalized_aliases:
                    score = 100
                else:
                    for alias in normalized_aliases:
                        if alias and alias in normalized_column:
                            score = max(score, 90)
                        elif normalized_column.startswith(alias) or normalized_column.endswith(alias):
                            score = max(score, 80)
                        elif alias and len(alias) > 3 and alias in normalized_column:
                            score = max(score, 70)

                    if score == 0:
                        field_tokens = [token for token in re.split(r'[^a-z0-9]+', field.lower()) if token and token not in {'and', 'the'}]
                        column_tokens = [token for token in re.split(r'[^a-z0-9]+', normalized_column) if token]
                        overlap = len(set(field_tokens) & set(column_tokens))
                        if overlap and overlap >= max(1, len(field_tokens) // 2):
                            score = 60

                if score > best_score:
                    best_score = score
                    best_match = column

            if best_score >= 70:
                mapping[field] = best_match

        return mapping
    
    @staticmethod
    def validate_mapping(mapping):
        """Validate that all required fields are mapped"""
        if not mapping:
            return False

        required_fields = set(DataProcessor.REQUIRED_FIELDS)
        provided_keys = set(mapping.keys())
        if not required_fields.issubset(provided_keys):
            return False

        for field in DataProcessor.REQUIRED_FIELDS:
            value = mapping.get(field)
            if not value:
                return False

        return True
    
    @staticmethod
    def process_data(upload, mapping):
        """
        Process and validate uploaded data based on column mapping
        """
        try:
            # Read file
            if upload.file_format == 'xlsx':
                df = pd.read_excel(upload.file)
            else:  # csv
                df = pd.read_csv(upload.file)
            
            # Rename columns according to mapping
            reverse_mapping = {v: k for k, v in mapping.items()}
            df = df.rename(columns=reverse_mapping)
            
            # Data quality checks
            quality_report = {
                'total_rows': len(df),
                'missing_values': df.isnull().sum().to_dict(),
                'data_types': df.dtypes.astype(str).to_dict(),
                'warnings': []
            }
            
            # Check for empty rows
            df = df.dropna(how='all')
            
            # Validate numeric columns
            numeric_cols = ['BS&W (%)', 'Net Oil (bopd)', 'Form.GLR (scf/bbl)', 
                          'Tubing Pressure (psi)', 'Flow Line Pressure (psi)']
            
            for col in numeric_cols:
                if col in df.columns:
                    try:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    except Exception as e:
                        quality_report['warnings'].append(f"Could not convert {col} to numeric: {str(e)}")
            
            # Validate dates
            try:
                df['Date'] = pd.to_datetime(df['Date'])
            except Exception as e:
                quality_report['warnings'].append(f"Could not parse dates: {str(e)}")
            
            return df, quality_report, None
            
        except Exception as e:
            logger.error(f"Error processing data: {str(e)}")
            return None, None, str(e)
    
    @staticmethod
    def create_preview(upload, mapping):
        """Create preview data (first 50 rows)"""
        df, quality_report, error = DataProcessor.process_data(upload, mapping)
        
        if error:
            return None, error
        
        # Sample first 50 rows
        sample = df.head(50).to_dict('records')
        
        # Convert any non-serializable types (e.g. Timestamp) to strings
        for row in sample:
            for key, value in row.items():
                if hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
                elif isinstance(value, (pd.Timestamp, pd.Period, pd.Interval)):
                    row[key] = str(value)
                elif pd.isna(value):
                    row[key] = None
        
        # Create preview record
        preview = PreviewData.objects.create(
            upload=upload,
            sample_data=sample,
            data_quality_report=quality_report
        )
        
        return preview, None
