import os
import pathlib
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaslift_config.settings')
django.setup()

from apps.data_upload.utils import DataProcessor
from apps.analysis.utils import TrendAnalyzer
from apps.analysis.models import AnalysisWeights

fp = pathlib.Path('test_data/data.csv')
print('File exists:', fp.exists())
with open(fp, 'rb') as f:
    rows = DataProcessor.read_file(f, 'csv')
print('Rows:', len(rows))
cols = DataProcessor.detect_columns(rows)
print('Columns:', cols)
mapping = DataProcessor.auto_map_columns(cols)
print('Auto-mapping:', mapping)
print('Valid mapping:', DataProcessor.validate_mapping(mapping))

# Create a dummy upload object with file-like attr for process_data
class DummyUpload:
    def __init__(self, path):
        self.file = open(path, 'rb')

upload = DummyUpload(fp)
processed_rows, quality_report, err = DataProcessor.process_data(upload, mapping)
print('Processed rows count:', len(processed_rows) if processed_rows else None)
print('Quality report keys:', list(quality_report.keys()) if quality_report else None)
print('Error:', err)

weights = AnalysisWeights(
    bsw_weight=100,
    oil_rate_weight=100,
    glr_weight=100,
    tubing_pressure_weight=50,
    economic_limit_oil_bopd=50,
    gas_constraint_mmscf=1.0,
)

well_name = rows[0].get('Well')
well_rows = [r for r in rows if r.get('Well') == well_name]
print('Well rows count for', well_name, len(well_rows))

result = TrendAnalyzer.analyze_well(
    well_rows,
    weights,
    base_choke_size='32/64',
    outlier_method='iqr',
    outlier_threshold=1.5,
)
print('Candidate score:', result.get('candidate_score'))
print('BSW trend:', result.get('bsw_trend'))
print('Oil trend:', result.get('oil_rate_trend'))
print('GLR trend:', result.get('glr_trend'))
print('Tubing pressure trend:', result.get('tubing_pressure_trend'))
print('Data quality score:', result.get('data_quality_score'))
