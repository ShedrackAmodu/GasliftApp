"""Generate sample well test data for Gas Lift Opportunity Automation System.

This script creates a sample CSV and Excel file with the required columns for upload.

Usage:
    python generate_sample_data.py

Outputs:
    sample_well_data.csv
    sample_well_data.xlsx
"""

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

OUTPUT_CSV = Path('sample_well_data.csv')
OUTPUT_XLSX = Path('sample_well_data.xlsx')

WELLS = ['Well_A', 'Well_B', 'Well_C', 'Well_D', 'Well_E']
TEST_STATUSES = ['Normal', 'Valid', 'OK', 'Producing', 'Active']
PROD_METHODS = ['Natural', 'ESP', 'Gas Lift', 'Natural', 'Natural']
CHOKE_SIZES = ['12/64"', '16/64"', '20/64"', '24/64"', '18/64"']


def generate_trend_values(base, slope, noise_scale, length):
    """Create a trend with optional noise."""
    x = np.arange(length)
    values = base + slope * x + np.random.normal(scale=noise_scale, size=length)
    return np.round(np.maximum(values, 0), 2)


def create_sample_data(num_points=12):
    rows = []
    start_date = datetime(2025, 1, 1)

    for well_index, well_id in enumerate(WELLS):
        base_bsw = 5 + well_index * 2
        base_oil = 200 + well_index * 50
        base_glr = 800 - well_index * 50
        base_tp = 1200 - well_index * 20
        prod_method = PROD_METHODS[well_index % len(PROD_METHODS)]
        choke_size = CHOKE_SIZES[well_index % len(CHOKE_SIZES)]

        for i in range(num_points):
            date = pd.Timestamp(start_date) + pd.DateOffset(months=i)
            bsw = generate_trend_values(base_bsw, 0.25 + 0.05 * well_index, 0.15, num_points)[i]
            net_oil = generate_trend_values(base_oil, -3 - well_index, 4, num_points)[i]
            glr = generate_trend_values(base_glr, -5 - well_index * 1.5, 8, num_points)[i]
            tubing_pressure = generate_trend_values(base_tp, -2 - well_index * 0.5, 6, num_points)[i]
            flow_line_pressure = max(40 + np.random.normal(scale=3), 20)
            test_status = TEST_STATUSES[i % len(TEST_STATUSES)]

            rows.append({
                'Well': well_id,
                'Date': date.strftime('%Y-%m-%d'),
                'BS&W (%)': bsw,
                'Net Oil (bopd)': net_oil,
                'Form.GLR (scf/bbl)': glr,
                'Prod Method': prod_method,
                'Test Status': test_status,
                'Tubing Pressure (psi)': tubing_pressure,
                'Flow Line Pressure (psi)': np.round(flow_line_pressure, 2),
                'Well Choke Size': choke_size,
            })

    return pd.DataFrame(rows)


def main():
    sample_df = create_sample_data(num_points=12)
    sample_df.to_csv(OUTPUT_CSV, index=False)
    sample_df.to_excel(OUTPUT_XLSX, index=False)
    print(f'Generated sample data files: {OUTPUT_CSV.resolve()}, {OUTPUT_XLSX.resolve()}')


if __name__ == '__main__':
    main()
