from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from django.db import transaction
from django.contrib import messages
import pandas as pd

from apps.data_upload.models import DataUpload, ColumnMapping, PreviewData
from .models import AnalysisSession, AnalysisWeights, WellTrendAnalysis
from .forms import AnalysisWeightsForm, AnalysisSessionForm
from .utils import TrendAnalyzer, SummaryGenerator


@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def adjust_weights(request, upload_id):
    """Adjust parameter weights - Step 4"""
    upload = get_object_or_404(DataUpload, id=upload_id, user=request.user)

    # Get or create analysis session
    # If there's a completed analysis for this upload, create a new one
    existing_analysis = AnalysisSession.objects.filter(
        upload=upload,
        user=request.user,
        status='pending'
    ).first()

    if existing_analysis:
        analysis = existing_analysis
    else:
        analysis = AnalysisSession.objects.create(
            upload=upload,
            user=request.user,
            status='pending'
        )

    # Get or create weights
    weights, w_created = AnalysisWeights.objects.get_or_create(analysis=analysis)

    if request.method == 'POST':
        form = AnalysisWeightsForm(request.POST, instance=weights)
        if form.is_valid():
            form.save()
            messages.success(request, 'Weights saved successfully.')
            return redirect('analysis:well_trends', analysis_id=analysis.id)
    else:
        form = AnalysisWeightsForm(instance=weights)

    context = {
        'form': form,
        'upload': upload,
        'analysis': analysis
    }

    return render(request, 'analysis/adjust_weights.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET"])
def well_trends(request, analysis_id):
    """View individual well trends - Step 5"""
    analysis = get_object_or_404(AnalysisSession, id=analysis_id, user=request.user)

    # Get the data
    try:
        col_mapping = ColumnMapping.objects.get(upload=analysis.upload)
        df = _load_data(analysis.upload, col_mapping.mapping)
    except ColumnMapping.DoesNotExist:
        return render(request, 'analysis/well_trends.html', {
            'analysis': analysis,
            'error': 'Column mapping not found. Please map your columns first.'
        })
    except Exception as e:
        return render(request, 'analysis/well_trends.html', {
            'analysis': analysis,
            'error': f'Error loading data: {str(e)}'
        })

    wells = df['Well'].unique() if 'Well' in df.columns else []

    if len(wells) == 0:
        return render(request, 'analysis/well_trends.html', {
            'analysis': analysis,
            'error': 'No wells found in the uploaded data. Please check your file.'
        })

    context = {
        'analysis': analysis,
        'wells': wells,
        'upload': analysis.upload
    }

    return render(request, 'analysis/well_trends.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET"])
def get_well_data(request, analysis_id, well_name):
    """API endpoint to get well trend data for charts"""
    analysis = get_object_or_404(AnalysisSession, id=analysis_id, user=request.user)

    try:
        col_mapping = ColumnMapping.objects.get(upload=analysis.upload)
        df = _load_data(analysis.upload, col_mapping.mapping)

        # Filter for well
        well_data = df[df['Well'] == well_name]

        if well_data.empty:
            return JsonResponse({'error': f'No data found for well: {well_name}'}, status=404)

        # Sort by date
        well_data = well_data.sort_values('Date')

        # Prepare chart data
        data = {
            'dates': well_data['Date'].dt.strftime('%Y-%m-%d').tolist() if 'Date' in well_data.columns else [],
            'bsw': _safe_series_to_list(well_data['BS&W (%)']) if 'BS&W (%)' in well_data.columns else [],
            'oil_rate': _safe_series_to_list(well_data['Net Oil (bopd)']) if 'Net Oil (bopd)' in well_data.columns else [],
            'glr': _safe_series_to_list(well_data['Form.GLR (scf/bbl)']) if 'Form.GLR (scf/bbl)' in well_data.columns else [],
            'tubing_pressure': _safe_series_to_list(well_data['Tubing Pressure (psi)']) if 'Tubing Pressure (psi)' in well_data.columns else [],
        }

        return JsonResponse(data)
    except ColumnMapping.DoesNotExist:
        return JsonResponse({'error': 'Column mapping not found'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required(login_url='accounts:login')
@require_POST
def run_analysis(request, analysis_id):
    """Run the analysis - Step 6"""
    analysis = get_object_or_404(AnalysisSession, id=analysis_id, user=request.user)

    try:
        with transaction.atomic():
            analysis.status = 'processing'
            analysis.started_at = timezone.now()
            analysis.save()

            # Get column mapping
            col_mapping = ColumnMapping.objects.get(upload=analysis.upload)
            weights = AnalysisWeights.objects.get(analysis=analysis)

            # Load data
            df = _load_data(analysis.upload, col_mapping.mapping)

            if df.empty:
                raise ValueError('No data found in the uploaded file.')

            # Delete any existing well trends for this analysis (prevents duplicates on re-run)
            WellTrendAnalysis.objects.filter(analysis=analysis).delete()

            # Analyze each well
            well_trends = []
            wells = df['Well'].unique()

            if len(wells) == 0:
                raise ValueError('No wells found in the data. Please check that the "Well" column is correctly mapped.')

            for well_id in wells:
                well_data = df[df['Well'] == well_id].sort_values('Date')

                if len(well_data) < 5:  # Need at least 5 data points
                    continue

                # Filter out invalid test statuses if column exists
                if 'Test Status' in well_data.columns:
                    valid_statuses = ['normal', 'valid', 'ok', 'good', 'producing', 'active', '']
                    well_data = well_data[well_data['Test Status'].str.lower().fillna('').isin(valid_statuses)]
                    if len(well_data) < 3:
                        continue

                # Analyze trends
                trends = TrendAnalyzer.analyze_well(well_data, weights)

                # Create well trend record
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
                )
                well_trends.append(trend_obj)

            if not well_trends:
                raise ValueError(
                    'No wells could be analyzed. Wells need at least 5 data points with valid test statuses. '
                    'Please check your data.'
                )

            # Sort and rank
            well_trends_sorted = sorted(well_trends, key=lambda x: x.candidate_score, reverse=True)
            for idx, trend in enumerate(well_trends_sorted, 1):
                trend.rank = idx
                trend.save()

            analysis.status = 'completed'
            analysis.completed_at = timezone.now()
            analysis.save()

        messages.success(request, f'Analysis completed successfully. {len(well_trends)} wells analyzed.')

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'analysis_id': str(analysis.id)})
        return redirect('results:view_results', analysis.id)

    except ColumnMapping.DoesNotExist:
        error_msg = 'Column mapping not found. Please map your columns first.'
        analysis.status = 'failed'
        analysis.error_message = error_msg
        analysis.completed_at = timezone.now()
        analysis.save()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'error': error_msg}, status=400)
        return render(request, 'analysis/well_trends.html', {
            'analysis': analysis,
            'error': error_msg
        })
    except Exception as e:
        analysis.status = 'failed'
        analysis.error_message = str(e)
        analysis.completed_at = timezone.now()
        analysis.save()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'error': str(e)}, status=400)
        return render(request, 'analysis/well_trends.html', {
            'analysis': analysis,
            'error': str(e)
        })


@login_required(login_url='accounts:login')
@require_http_methods(["GET"])
def my_analyses(request):
    """List user's analysis sessions"""
    analyses = AnalysisSession.objects.filter(user=request.user)
    return render(request, 'analysis/my_analyses.html', {'analyses': analyses})


@login_required(login_url='accounts:login')
@require_POST
def delete_analysis(request, analysis_id):
    """Delete an analysis session"""
    analysis = get_object_or_404(AnalysisSession, id=analysis_id, user=request.user)
    analysis.delete()
    messages.success(request, 'Analysis deleted successfully.')
    return redirect('analysis:my_analyses')


def _load_data(upload, mapping):
    """Helper to load and map data from upload"""
    if upload.file_format == 'xlsx':
        df = pd.read_excel(upload.file)
    else:
        df = pd.read_csv(upload.file)

    if df.empty:
        return df

    # Rename columns
    reverse_mapping = {v: k for k, v in mapping.items()}
    df = df.rename(columns=reverse_mapping)

    # Convert date
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    # Convert numeric columns
    numeric_cols = ['BS&W (%)', 'Net Oil (bopd)', 'Form.GLR (scf/bbl)',
                   'Tubing Pressure (psi)', 'Flow Line Pressure (psi)']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def _safe_series_to_list(series):
    """Convert pandas Series to list, handling NaN values."""
    return [None if pd.isna(x) else x for x in series.tolist()]