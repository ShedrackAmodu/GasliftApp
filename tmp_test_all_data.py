import os, pathlib
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaslift_config.settings')
import django
django.setup()
from apps.data_upload.utils import DataProcessor, _parse_date, _coerce_numeric
from apps.analysis.utils import TrendAnalyzer
from apps.analysis.models import AnalysisWeights
from collections import Counter

test_files = [
    'test_data/production_data.csv',
    'test_data/production_data.xlsx',
    'test_data/well_data.xlsx',
    'test_data/data.xlsx',
]

for fp_str in test_files:
    fp = pathlib.Path(fp_str)
    ext = fp.suffix.lstrip('.')
    print(f'\n=== {fp.name} ===')
    
    with open(fp, 'rb') as f:
        rows = DataProcessor.read_file(f, ext)
    print(f'Rows: {len(rows)}, Columns: {list(rows[0].keys()) if rows else []}')
    
    # Simulate _load_data
    mapping = {field: field for field in DataProcessor.REQUIRED_FIELDS if field in rows[0].keys()}
    if len(mapping) < 10:
        mapping = DataProcessor.auto_map_columns(list(rows[0].keys()))
        print(f'Auto-mapped: {len(mapping)} fields')
    
    reverse_mapping = {v: k for k, v in mapping.items()}
    mapped_rows = []
    for row in rows:
        new_row = {}
        for orig_key, value in row.items():
            if orig_key in reverse_mapping:
                new_row[reverse_mapping[orig_key]] = value
            else:
                new_row[orig_key] = value
        mapped_rows.append(new_row)
    
    # Convert dates
    for row in mapped_rows:
        if row.get('Date') is not None and row['Date'] != '':
            try:
                row['Date'] = _parse_date(row['Date'])
            except (ValueError, TypeError):
                row['Date'] = None
        else:
            row['Date'] = None
    
    # Convert numerics
    numeric_cols = ['BS&W (%)', 'Net Oil (bopd)', 'Form.GLR (scf/bbl)', 'Tubing Pressure (psi)', 'Flow Line Pressure (psi)']
    for col in numeric_cols:
        for row in mapped_rows:
            if col in row:
                val = row[col]
                if val is not None and val != '':
                    row[col] = _coerce_numeric(val)
                else:
                    row[col] = None
    
    none_dates = sum(1 for r in mapped_rows if r.get('Date') is None)
    print(f'None dates: {none_dates}/{len(mapped_rows)}')
    
    well_counts = Counter(r.get('Well') for r in mapped_rows if r.get('Well'))
    print(f'Unique wells: {len(well_counts)}')
    
    weights = AnalysisWeights(
        bsw_weight=100, oil_rate_weight=100, glr_weight=100,
        tubing_pressure_weight=50, economic_limit_oil_bopd=50,
        gas_constraint_mmscf=1.0,
    )
    
    for well_name, count in well_counts.most_common():
        if count >= 5:
            well_rows = [r for r in mapped_rows if r.get('Well') == well_name]
            well_rows.sort(key=lambda r: r.get('Date') or '')
            trends = TrendAnalyzer.analyze_well(well_rows, weights)
            bsw = trends.get('bsw_trend', '?')
            oil = trends.get('oil_rate_trend', '?')
            glr = trends.get('glr_trend', '?')
            tp = trends.get('tubing_pressure_trend', '?')
            score = trends.get('candidate_score', 0)
            print(f'Well {well_name}: BSW={bsw}, Oil={oil}, GLR={glr}, TP={tp}, Score={score:.2f}')
            break