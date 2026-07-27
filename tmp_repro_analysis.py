import os
import pathlib

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaslift_config.settings')
import django

django.setup()

from apps.data_upload.utils import DataProcessor
from apps.analysis.utils import TrendAnalyzer
from apps.analysis.models import AnalysisWeights

fp = pathlib.Path('test_data/production_data.csv')
print('File exists:', fp.exists())
if not fp.exists():
    raise SystemExit('Missing production_data.csv')

with open(fp, 'rb') as f:
    rows = DataProcessor.read_file(f, 'csv')
print('Rows:', len(rows))
print('Columns:', list(rows[0].keys()) if rows else None)

cols = DataProcessor.detect_columns(rows)
print('Detected columns:', cols)

mapped = DataProcessor.auto_map_columns(cols)
for field, candidates in mapped.items():
    print(field, '->', candidates[:3])

mapping = {field: field for field in DataProcessor.REQUIRED_FIELDS}
print('Best mapping:', mapping)

class DummyUpload:
    def __init__(self, path, file_format):
        self.file = open(path, 'rb')
        self.file_format = file_format

upload = DummyUpload(fp, 'csv')
processed_rows, quality_report, error = DataProcessor.process_data(upload, mapping)
print('Processed rows:', len(processed_rows) if processed_rows else None)
print('Quality report:', quality_report)
print('Error:', error)

if not processed_rows:
    raise SystemExit('No processed rows.')

# Find wells with at least 5 points
well_counts = {}
for r in processed_rows:
    well = r.get('Well')
    well_counts[well] = well_counts.get(well, 0) + 1

candidates = [(well, count) for well, count in well_counts.items() if count >= 5]
print('Candidate wells >=5 rows:', len(candidates))
for well, count in sorted(candidates, key=lambda x: -x[1])[:10]:
    print('  ', well, count)

if not candidates:
    raise SystemExit('No wells with >=5 rows')

# analyze first candidate well
well_name = sorted(candidates, key=lambda x: (-x[1], x[0]))[0][0]
well_rows = [r for r in processed_rows if r.get('Well') == well_name]
well_rows.sort(key=lambda r: r.get('Date') or '')
print('Analyzing well:', well_name, 'rows:', len(well_rows))

weights = AnalysisWeights(
    bsw_weight=100,
    oil_rate_weight=100,
    glr_weight=100,
    tubing_pressure_weight=50,
    economic_limit_oil_bopd=50,
    gas_constraint_mmscf=1.0,
)
trends = TrendAnalyzer.analyze_well(
    well_rows,
    weights,
    base_choke_size='32/64',
    outlier_method='iqr',
    outlier_threshold=1.5,
)
print('Trend result for', well_name)
for k, v in trends.items():
    if k in ['candidate_score', 'bsw_trend', 'bsw_slope', 'oil_rate_trend', 'oil_rate_slope', 'glr_trend', 'glr_slope', 'tubing_pressure_trend', 'tubing_pressure_slope', 'data_quality_score']:
        print(' ', k, ':', v)

print('Sample rows:')
for row in well_rows[:5]:
    print('  ', {k: row.get(k) for k in ['Date','BS&W (%)','Net Oil (bopd)','Form.GLR (scf/bbl)','Tubing Pressure (psi)','Well Choke Size']})
