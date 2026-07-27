import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'gaslift_config.settings'
import django
django.setup()
from apps.data_upload.utils import _parse_date
from apps.analysis.utils import TrendAnalyzer

cases = ['2024-01-01', '01/02/2024', '02-01-2024', '20240102', '2024-01-02T00:00:00Z', '02 Jan 2024']
for c in cases:
    try:
        d = _parse_date(c)
        print(c, '->', d)
    except Exception as e:
        print(c, '-> ERROR', type(e).__name__, e)

for label, series in [('invalid dates', ['x']*5)]:
    try:
        trend, tau, p_value = TrendAnalyzer.mann_kendall_test([100, 90, 80, 70, 60], time_series=series)
        slope = TrendAnalyzer.sen_slope([100, 90, 80, 70, 60], time_series=series)
        print('Trend', trend, 'tau', tau, 'p', p_value, 'slope', slope)
    except Exception as e:
        print('Trend fallback ERROR', type(e).__name__, e)
