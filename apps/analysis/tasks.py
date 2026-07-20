"""
Celery tasks for async analysis processing.
"""
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import datetime
import logging

from .models import AnalysisSession, AnalysisWeights, WellTrendAnalysis
from .utils import TrendAnalyzer, SummaryGenerator

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def run_analysis_async(self, analysis_id, user_id, options=None):
    """
    Run analysis asynchronously via Celery.
    Returns task progress and results.
    """
    from apps.data_upload.models import ColumnMapping
    from apps.data_upload.utils import DataProcessor, _parse_date
    
    if options is None:
        options = {}
    
    try:
        analysis = AnalysisSession.objects.get(id=analysis_id)
        analysis.status = 'processing'
        analysis.started_at = timezone.now()
        analysis.save()
        
        self.update_state(state='PROGRESS', meta={'progress': 0, 'status': 'Loading data...'})
        
        col_mapping = ColumnMapping.objects.get(upload=analysis.upload)
        weights = AnalysisWeights.objects.get(analysis=analysis)
        rows = _load_data_celery(analysis.upload, col_mapping.mapping, DataProcessor, _parse_date)
        
        if not rows:
            raise ValueError('No data found in the uploaded file.')
        
        base_choke_size = options.get('base_choke_size') or None
        outlier_method = options.get('outlier_method', 'iqr')
        outlier_threshold = float(options.get('outlier_threshold', 1.5))
        
        # TrendAnalyzer.analyze_well will apply choke normalization per well
        # if base_choke_size is specified, so avoid double-normalizing rows here.
        WellTrendAnalysis.objects.filter(analysis=analysis).delete()
        
        well_trends = []
        wells_data = _group_wells_celery(rows)
        wells = list(wells_data.keys())
        total_wells = len(wells)
        skipped_wells = 0
        
        for idx, well_id in enumerate(wells):
            well_rows = wells_data[well_id]
            
            # Update progress
            progress = int((idx / total_wells) * 100)
            self.update_state(
                state='PROGRESS',
                meta={'progress': progress, 'status': f'Analyzing {well_id}...'}
            )
            
            if len(well_rows) < 5:
                skipped_wells += 1
                continue
            
            trends = TrendAnalyzer.analyze_well(
                well_rows, weights,
                base_choke_size=base_choke_size,
                outlier_method=outlier_method,
                outlier_threshold=outlier_threshold,
            )
            
            trend_obj = WellTrendAnalysis.objects.create(
                analysis=analysis,
                well_id=well_id,
                bsw_trend=trends['bsw_trend'],
                bsw_slope=trends['bsw_slope'],
                bsw_magnitude=trends['bsw_magnitude'],
                bsw_flag=trends['bsw_flag'],
                oil_rate_trend=trends['oil_rate_trend'],
                oil_rate_slope=trends['oil_rate_slope'],
                oil_rate_magnitude=trends['oil_rate_magnitude'],
                oil_rate_flag=trends['oil_rate_flag'],
                glr_trend=trends['glr_trend'],
                glr_slope=trends['glr_slope'],
                glr_magnitude=trends['glr_magnitude'],
                glr_flag=trends['glr_flag'],
                tubing_pressure_trend=trends['tubing_pressure_trend'],
                tubing_pressure_slope=trends['tubing_pressure_slope'],
                tubing_pressure_magnitude=trends['tubing_pressure_magnitude'],
                candidate_score=trends['candidate_score'],
                summary_comment=SummaryGenerator.generate_comment(trends),
                prod_method=trends.get('prod_method', ''),
                test_status=trends.get('test_status', ''),
                flow_line_pressure=trends.get('flow_line_pressure'),
                well_choke_size=trends.get('well_choke_size', ''),
                is_choke_normalized=trends.get('is_choke_normalized', False),
                data_quality_score=trends.get('data_quality_score', 100.0),
                outlier_count=trends.get('outlier_count', 0),
                original_values=trends.get('original_values', {}),
                corrected_values=trends.get('corrected_values', {}),
                rejected_indices=trends.get('rejected_indices', {}),
                liquid_loading_flag=trends.get('liquid_loading_flag', False),
                days_to_economic_limit=trends.get('days_to_economic_limit'),
            )
            well_trends.append(trend_obj)
        
        # Rank
        well_trends_sorted = sorted(well_trends, key=lambda x: x.candidate_score, reverse=True)
        for rank_idx, trend in enumerate(well_trends_sorted, 1):
            trend.rank = rank_idx
            trend.save()
        
        analysis.status = 'completed'
        analysis.completed_at = timezone.now()
        analysis.save()
        
        return {
            'status': 'completed',
            'analysis_id': str(analysis.id),
            'wells_analyzed': len(well_trends),
            'skipped_wells': skipped_wells,
        }
        
    except Exception as e:
        try:
            analysis = AnalysisSession.objects.get(id=analysis_id)
            analysis.status = 'failed'
            analysis.error_message = str(e)
            analysis.completed_at = timezone.now()
            analysis.save()
        except Exception:
            pass
        
        raise e


def _load_data_celery(upload, mapping, DataProcessor, _parse_date):
    """Load data helper for Celery task."""
    rows = DataProcessor.read_file(upload.file, upload.file_format)
    if not rows:
        return []
    
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
    
    for row in mapped_rows:
        if row.get('Date') is not None and row['Date'] != '':
            try:
                row['Date'] = _parse_date(row['Date'])
            except (ValueError, TypeError):
                row['Date'] = None
        else:
            row['Date'] = None
    
    numeric_cols = ['BS&W (%)', 'Net Oil (bopd)', 'Form.GLR (scf/bbl)',
                   'Tubing Pressure (psi)', 'Flow Line Pressure (psi)']
    for col in numeric_cols:
        for row in mapped_rows:
            if col in row:
                val = row[col]
                if val is not None and val != '':
                    try:
                        row[col] = float(val)
                    except (ValueError, TypeError):
                        row[col] = None
                else:
                    row[col] = None
    return mapped_rows


def _group_wells_celery(rows):
    """Group rows by well."""
    well_data = {}
    for r in rows:
        well = r.get('Well')
        if well:
            if well not in well_data:
                well_data[well] = []
            well_data[well].append(r)
    
    for well_id in well_data:
        well_data[well_id].sort(key=lambda x: x.get('Date', datetime.min) if x.get('Date') else datetime.min)
    
    return well_data