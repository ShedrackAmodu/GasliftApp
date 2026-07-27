from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from django.db import transaction
from django.contrib import messages
from datetime import datetime
import json
import re
import numpy as np
import csv
import io

from apps.data_upload.models import DataUpload, ColumnMapping, PreviewData
from .models import AnalysisSession, AnalysisWeights, WellTrendAnalysis, PVTProperties, CompletionData
from .forms import AnalysisWeightsForm, AnalysisSessionForm, CompletionDataForm, PVTPropertiesForm
from .utils import TrendAnalyzer, SummaryGenerator
from .pvt import PVTProperties as PVT
from .ipr_calculator import IPRCalculator, LiquidLoadingDiagnostics
from .completion import CompletionFeasibilityChecker
from .sensitivity import MonteCarloSensitivity
from apps.data_upload.utils import DataProcessor, _parse_date, _coerce_numeric


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
        rows = _load_data(analysis.upload, col_mapping.mapping)
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

    wells = _unique_wells(rows)
    selected_wells = analysis.selected_wells or []

    if len(wells) == 0:
        return render(request, 'analysis/well_trends.html', {
            'analysis': analysis,
            'error': 'No wells found in the uploaded data. Please check your file.'
        })

    context = {
        'analysis': analysis,
        'wells': wells,
        'selected_wells': selected_wells,
        'upload': analysis.upload,
        'weights': AnalysisWeights.objects.filter(analysis=analysis).first(),
        'pvt_configured': PVTProperties.objects.filter(analysis=analysis).exists(),
        'completion_uploaded': CompletionData.objects.filter(analysis=analysis).exists(),
    }

    return render(request, 'analysis/well_trends.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET"])
def get_well_data(request, analysis_id, well_name):
    """API endpoint to get well trend data for charts"""
    analysis = get_object_or_404(AnalysisSession, id=analysis_id, user=request.user)

    def _format_date(value):
        if value in (None, ''):
            return ''
        try:
            return str(_parse_date(value)).split()[0]
        except (ValueError, TypeError):
            return ''

    try:
        col_mapping = ColumnMapping.objects.get(upload=analysis.upload)
        rows = _load_data(analysis.upload, col_mapping.mapping)
        well_name_normalized = _normalize_well_id(well_name)
        well_rows = [r for r in rows if _normalize_well_id(r.get('Well')) == well_name_normalized]
        well_rows.sort(key=lambda r: _parse_date(r.get('Date')) if r.get('Date') not in (None, '') else datetime.min)
        dates = [_format_date(r.get('Date')) for r in well_rows]

        # Try to get pre-computed analysis from database
        trend = None
        for candidate in WellTrendAnalysis.objects.filter(analysis=analysis):
            if _normalize_well_id(candidate.well_id) == well_name_normalized:
                trend = candidate
                break

        if trend and trend.original_values is not None and trend.original_values:
            series_length = len(dates)
            data = {
                'dates': dates,
                'bsw': _normalize_chart_series(trend.corrected_values.get('bsw', trend.original_values.get('bsw', [])), series_length),
                'oil_rate': _normalize_chart_series(trend.corrected_values.get('oil_rate', trend.original_values.get('oil_rate', [])), series_length),
                'glr': _normalize_chart_series(trend.corrected_values.get('glr', trend.original_values.get('glr', [])), series_length),
                'tubing_pressure': _normalize_chart_series(trend.corrected_values.get('tp', trend.original_values.get('tp', [])), series_length),
                'rejected_indices': trend.rejected_indices or {},
                'is_choke_normalized': trend.is_choke_normalized,
                'data_quality_score': trend.data_quality_score,
                'liquid_loading_flag': trend.liquid_loading_flag,
                'critical_velocity': trend.critical_velocity,
                'actual_velocity': trend.actual_velocity,
                'days_to_economic_limit': trend.days_to_economic_limit,
                'projected_oil_rate_6mo': trend.projected_oil_rate_6mo,
                'recommended_gas_mmscf': trend.recommended_gas_mmscf,
                'completion_feasibility': trend.completion_feasibility,
                'pvt_configured': PVTProperties.objects.filter(analysis=analysis).exists(),
                'completion_uploaded': CompletionData.objects.filter(analysis=analysis, well_id=well_name).exists(),
            }
            return JsonResponse(data)

        # Fallback to raw data
        data = {
            'dates': dates,
            'bsw': _normalize_chart_series([r.get('BS&W (%)') for r in well_rows], len(dates)),
            'oil_rate': _normalize_chart_series([r.get('Net Oil (bopd)') for r in well_rows], len(dates)),
            'glr': _normalize_chart_series([r.get('Form.GLR (scf/bbl)') for r in well_rows], len(dates)),
            'tubing_pressure': _normalize_chart_series([r.get('Tubing Pressure (psi)') for r in well_rows], len(dates)),
            'rejected_indices': {},
            'is_choke_normalized': False,
            'data_quality_score': 100.0,
            'liquid_loading_flag': False,
            'critical_velocity': None,
            'actual_velocity': None,
            'days_to_economic_limit': None,
            'projected_oil_rate_6mo': None,
            'recommended_gas_mmscf': None,
            'completion_feasibility': 'unknown',
            'pvt_configured': PVTProperties.objects.filter(analysis=analysis).exists(),
            'completion_uploaded': CompletionData.objects.filter(analysis=analysis, well_id=well_name).exists(),
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
            weights, _ = AnalysisWeights.objects.get_or_create(analysis=analysis)
            completion_records = {}
            for completion in CompletionData.objects.filter(analysis=analysis):
                completion_records[_normalize_well_id(completion.well_id)] = completion

            # Load data
            rows = _load_data(analysis.upload, col_mapping.mapping)
            if rows is None:
                rows = []

            if not rows:
                raise ValueError('No data found in the uploaded file.')

            # Delete any existing well trends for this analysis (prevents duplicates on re-run)
            WellTrendAnalysis.objects.filter(analysis=analysis).delete()

            # Get selected wells from POST data and save to model.
            selected_wells = []
            post_wells = request.POST.getlist('selected_wells')
            if post_wells:
                if len(post_wells) == 1:
                    raw = post_wells[0]
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, list):
                            selected_wells = [str(item) for item in parsed if item]
                        elif parsed:
                            selected_wells = [str(parsed)]
                    except (json.JSONDecodeError, TypeError, ValueError):
                        if isinstance(raw, str) and raw.strip().startswith('[') and raw.strip().endswith(']'):
                            try:
                                selected_wells = [s.strip() for s in raw.strip('[]').split(',') if s.strip()]
                            except Exception:
                                selected_wells = [raw]
                        else:
                            selected_wells = [raw]
                else:
                    selected_wells = [str(v) for v in post_wells if v]
            elif request.POST.get('selected_wells'):
                raw = request.POST.get('selected_wells')
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        selected_wells = [str(item) for item in parsed if item]
                except (json.JSONDecodeError, TypeError, ValueError):
                    if isinstance(raw, str) and raw.strip():
                        selected_wells = [raw.strip()]

            if not selected_wells and analysis.selected_wells:
                selected_wells = analysis.selected_wells

            if not selected_wells:
                raise ValueError('No wells selected. Please select one or more wells on the Well Trends page before running the analysis.')

            # Store selected wells on the analysis session for later use
            analysis.selected_wells = selected_wells
            analysis.save(update_fields=['selected_wells'])

            # Extract preprocessing params from saved weights or form submission
            base_choke_size = getattr(weights, 'base_choke_size', '') or request.POST.get('base_choke_size', '').strip() or None
            outlier_method = getattr(weights, 'outlier_method', '') or request.POST.get('outlier_method', 'iqr')
            try:
                outlier_threshold = float(getattr(weights, 'outlier_threshold', request.POST.get('outlier_threshold', 1.5)))
            except (TypeError, ValueError):
                outlier_threshold = 1.5
            
            # Choke normalization is handled within TrendAnalyzer.analyze_well
            # for each well when base_choke_size is provided.
            
            # Get optional PVT properties if they exist
            pvt_props = None
            try:
                pvt_model = PVTProperties.objects.get(analysis=analysis)
                pvt_props = PVT(
                    api_gravity=pvt_model.api_gravity,
                    gas_specific_gravity=pvt_model.gas_specific_gravity,
                    water_salinity=pvt_model.water_salinity,
                    temperature_f=pvt_model.temperature,
                    tubing_diameter=pvt_model.tubing_diameter
                )
            except PVTProperties.DoesNotExist:
                # Notify user that PVT properties are not configured - diagnostics will be skipped
                messages.warning(request, 'PVT properties not configured. Liquid-loading diagnostics and gas recommendations will be skipped. Configure PVT properties to enable these diagnostics.')

            # Gas constraint for knapsack optimization
            gas_constraint_mmscf = getattr(weights, 'gas_constraint_mmscf', None)

            # Analyze each well
            well_trends = []
            wells = _unique_wells(rows)
            
            # Filter to only selected wells if any were specified
            if selected_wells:
                wells = [w for w in wells if w in selected_wells]
            
            skipped_wells = 0

            if len(wells) == 0:
                raise ValueError('No wells found in the data. Please check that the "Well" column is correctly mapped.')

            for well_id in wells:
                well_rows = [r for r in rows if _normalize_well_id(r.get('Well')) == well_id]
                well_rows.sort(key=lambda r: _parse_date(r.get('Date', '')) if r.get('Date') else datetime.min)

                # Skip wells with insufficient valid rows before analysis
                if not well_rows:
                    skipped_wells += 1
                    continue

                if len(well_rows) < 5:  # Need at least 5 data points
                    skipped_wells += 1
                    continue

                # Filter out invalid test statuses if column exists
                if any(r.get('Test Status') is not None for r in well_rows):
                    valid_statuses = ['normal', 'valid', 'ok', 'good', 'producing', 'active', '']
                    filtered_rows = [
                        r for r in well_rows
                        if str(r.get('Test Status', '')).lower().strip() in valid_statuses
                    ]
                    if len(filtered_rows) < 3:
                        skipped_wells += 1
                        continue
                    well_rows = filtered_rows

                # Ensure the well data still contains the expected numeric fields
                if not any(r.get('Net Oil (bopd)') is not None for r in well_rows):
                    skipped_wells += 1
                    continue

                # Analyze trends with preprocessing options
                trends = TrendAnalyzer.analyze_well(
                    well_rows,
                    weights,
                    base_choke_size=base_choke_size,
                    outlier_method=outlier_method,
                    outlier_threshold=outlier_threshold,
                )

                # Calculate IPR and liquid loading diagnostics
                pi_trend = 'no_trend'
                pi_slope = 0
                liquid_loading_flag = False
                
                if pvt_props:
                    # Average GLR and tubing pressure for liquid loading
                    glr_values = [r.get('Form.GLR (scf/bbl)') for r in well_rows if r.get('Form.GLR (scf/bbl)') is not None]
                    tp_values = [r.get('Tubing Pressure (psi)') for r in well_rows if r.get('Tubing Pressure (psi)') is not None]
                    
                    avg_glr = sum(glr_values) / len(glr_values) if glr_values else None
                    avg_tp = sum(tp_values) / len(tp_values) if tp_values else None
                    
                    if avg_glr and avg_tp:
                        oil_values = [r.get('Net Oil (bopd)') for r in well_rows if r.get('Net Oil (bopd)') is not None]
                        avg_oil = sum(oil_values) / len(oil_values) if oil_values else None
                        gas_rate_mmscfd = None
                        if avg_oil and avg_oil > 0:
                            gas_rate_mmscfd = (avg_glr * avg_oil) / 1000000.0
                        liquid_loader = LiquidLoadingDiagnostics(pvt_props, pvt_props.tubing_diameter)
                        ll_result = liquid_loader.analyze_well(
                            avg_glr_scf_bbl=avg_glr,
                            avg_tubing_pressure_psi=avg_tp,
                            gas_rate_mmscfd=gas_rate_mmscfd,
                            oil_rate_bopd=avg_oil,
                        )
                        liquid_loading_flag = ll_result.get('liquid_loading_flag', False)
                        trends['critical_velocity'] = ll_result.get('critical_velocity')
                        trends['actual_velocity'] = ll_result.get('actual_velocity')
                        trends['critical_glr'] = ll_result.get('critical_glr')
                        trends['actual_glr'] = ll_result.get('actual_glr')
                        trends['diagnosis'] = ll_result.get('diagnosis')
                        trends['recommended_gas_mmscf'] = ll_result.get('recommended_gas_mmscf')
                        trends['gas_utilization_efficiency'] = ll_result.get('gas_utilization_efficiency')
                    
                    # PI calculation if reservoir pressure data available
                    rp_values = [r.get('Reservoir Pressure (psi)') for r in well_rows if r.get('Reservoir Pressure (psi)') is not None]
                    bhp_values = [r.get('Flowing BHP (psi)') for r in well_rows if r.get('Flowing BHP (psi)') is not None]
                    oil_values = [r.get('Net Oil (bopd)') for r in well_rows if r.get('Net Oil (bopd)') is not None]
                    
                    if rp_values and bhp_values and oil_values:
                        avg_rp = sum(rp_values) / len(rp_values)
                        avg_bhp = sum(bhp_values) / len(bhp_values)
                        avg_oil = sum(oil_values) / len(oil_values)
                        
                        pi = IPRCalculator.calculate_pi(avg_oil, avg_rp, avg_bhp)
                        if pi:
                            trends['productivity_index'] = pi
                            trends['static_reservoir_pressure'] = avg_rp
                            trends['flowing_bhp'] = avg_bhp
                            
                            # Estimate gas rate from GLR
                            if avg_glr and avg_oil > 0:
                                gas_rate_mmscfd = (avg_glr * avg_oil) / 1000000  # Convert scf/bbl to MMscf/d
                                recommended_gas = gas_rate_mmscfd * 0.4  # 40% of current gas rate
                                trends['recommended_gas_mmscf'] = round(recommended_gas, 3)
                                trends['gas_utilization_efficiency'] = 85.0  # Placeholder

                # Economic limit forecasting using Sen's slope
                oil_series = [r.get('Net Oil (bopd)') for r in well_rows]
                oil_slope = trends.get('oil_rate_slope', 0)
                if oil_slope < 0:  # Declining
                    corrected_oil_series = trends.get('corrected_values', {}).get('oil_rate')
                    if corrected_oil_series and len(corrected_oil_series) > 0:
                        # Last non-None value in corrected series
                        current_oil = next((v for v in reversed(corrected_oil_series) if v is not None), None)
                    else:
                        current_oil = None
                    if current_oil is None:
                        current_oil = well_rows[-1].get('Net Oil (bopd)')
                    if current_oil is not None and weights.economic_limit_oil_bopd is not None and weights.economic_limit_oil_bopd > 0 and current_oil > weights.economic_limit_oil_bopd:
                        days_to_limit = (current_oil - weights.economic_limit_oil_bopd) / abs(oil_slope)
                        trends['days_to_economic_limit'] = max(0, int(days_to_limit))
                        projected_6mo = current_oil + oil_slope * 180
                        trends['projected_oil_rate_6mo'] = max(0, round(projected_6mo, 2))

                # Determine completion feasibility using uploaded completion data if available
                trends['completion_feasibility'] = 'unknown'
                completion_record = completion_records.get(_normalize_well_id(well_id))
                if completion_record:
                    trends['completion_feasibility'] = completion_record.feasibility_flag or 'unknown'

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
                    is_choke_normalized=trends.get('is_choke_normalized', False),
                    data_quality_score=trends.get('data_quality_score', 100.0),
                    outlier_count=trends.get('outlier_count', 0),
                    original_values=trends.get('original_values', {}),
                    corrected_values=trends.get('corrected_values', {}),
                    rejected_indices=trends.get('rejected_indices', {}),
                    # Reservoir and IPR
                    static_reservoir_pressure=trends.get('static_reservoir_pressure'),
                    flowing_bhp=trends.get('flowing_bhp'),
                    productivity_index=trends.get('productivity_index'),
                    # Liquid loading
                    liquid_loading_flag=liquid_loading_flag,
                    critical_velocity=trends.get('critical_velocity'),
                    actual_velocity=trends.get('actual_velocity'),
                    # Economic
                    days_to_economic_limit=trends.get('days_to_economic_limit'),
                    projected_oil_rate_6mo=trends.get('projected_oil_rate_6mo'),
                    # Gas allocation
                    recommended_gas_mmscf=trends.get('recommended_gas_mmscf'),
                    gas_utilization_efficiency=trends.get('gas_utilization_efficiency', 0),
                    # Feasibility
                    completion_feasibility=trends.get('completion_feasibility', 'unknown'),
                )
                well_trends.append(trend_obj)

            if not well_trends:
                raise ValueError(
                    'No wells could be analyzed. Wells need at least 5 data points with valid test statuses. '
                    'Please check your data.'
                )

            # Gas allocation knapsack optimization
            if gas_constraint_mmscf and gas_constraint_mmscf > 0:
                # Only run knapsack if at least one well has a recommended gas estimate
                candidates_with_gas = [t for t in well_trends if getattr(t, 'recommended_gas_mmscf', None) and t.recommended_gas_mmscf > 0]
                if not candidates_with_gas:
                    messages.warning(request, 'Gas allocation skipped: no wells have recommended gas estimates (ensure PVT is configured and liquid-loading diagnostics ran). Results will be ranked by candidate score instead.')
                    well_trends_sorted = sorted(well_trends, key=lambda x: x.candidate_score, reverse=True)
                    for idx, trend in enumerate(well_trends_sorted, 1):
                        trend.rank = idx
                else:
                    _run_gas_knapsack(well_trends, gas_constraint_mmscf)
            else:
                # Default ranking by candidate score
                well_trends_sorted = sorted(well_trends, key=lambda x: x.candidate_score, reverse=True)
                for idx, trend in enumerate(well_trends_sorted, 1):
                    trend.rank = idx

            # Save all records (ranks + all other fields)
            for trend in well_trends:
                trend.save()

            analysis.status = 'completed'
            analysis.completed_at = timezone.now()
            analysis.save()

        summary_msg = f'Analysis completed successfully. {len(well_trends)} wells analyzed.'
        if skipped_wells > 0:
            summary_msg += f' {skipped_wells} well(s) were skipped because they did not meet the minimum data or status criteria.'
        messages.success(request, summary_msg)

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
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Analysis failed for {analysis.id}: {e}", exc_info=True)
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


def _run_gas_knapsack(well_trends, gas_constraint_mmscf):
    """
    Greedy knapsack to allocate limited gas to maximize incremental oil gain.
    Simplified: assumes recommended_gas_mmscf is gas requirement.
    """
    try:
        # Prepare candidate list with calculated efficiency
        candidates = []
        for trend in well_trends:
            if trend.recommended_gas_mmscf and trend.recommended_gas_mmscf > 0:
                efficiency = trend.candidate_score / trend.recommended_gas_mmscf
                candidates.append((trend, efficiency, trend.recommended_gas_mmscf))
            else:
                trend.gas_utilization_efficiency = 0.0

        # Sort by efficiency, then by score for tie-breaking
        candidates.sort(key=lambda x: (x[1], x[0].candidate_score), reverse=True)

        remaining_gas = gas_constraint_mmscf
        allocated_trends = []
        rank = 1

        for trend, efficiency, gas_req in candidates:
            if gas_req <= remaining_gas:
                trend.rank = rank
                trend.gas_utilization_efficiency = min(efficiency * 100, 100)
                remaining_gas -= gas_req
                allocated_trends.append(trend)
                rank += 1
            else:
                # Do not allocate if candidate exceeds remaining capacity
                trend.gas_utilization_efficiency = 0.0

        # Assign ranks for unallocated wells by candidate score
        unallocated = [t for t in well_trends if t not in allocated_trends]
        unallocated.sort(key=lambda t: t.candidate_score, reverse=True)
        for trend in unallocated:
            trend.rank = rank
            trend.gas_utilization_efficiency = trend.gas_utilization_efficiency or 0.0
            rank += 1

    except Exception:
        # Fallback to simple ranking
        well_trends_sorted = sorted(well_trends, key=lambda x: x.candidate_score, reverse=True)
        for idx, trend in enumerate(well_trends_sorted, 1):
            trend.rank = idx


@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def configure_pvt(request, analysis_id):
    """Configure PVT fluid properties - Step 4a"""
    analysis = get_object_or_404(AnalysisSession, id=analysis_id, user=request.user)
    
    pvt, created = PVTProperties.objects.get_or_create(analysis=analysis)
    
    if request.method == 'POST':
        form = PVTPropertiesForm(request.POST, instance=pvt)
        if form.is_valid():
            form.save()
            messages.success(request, 'PVT properties saved successfully. Liquid loading diagnostics will use these values.')
            return redirect('analysis:well_trends', analysis_id=analysis.id)
    else:
        form = PVTPropertiesForm(instance=pvt)
    
    context = {
        'form': form,
        'analysis': analysis,
    }
    return render(request, 'analysis/configure_pvt.html', context)


def _persist_completion_record(analysis, well_id, mandrel_depths, packer_depth, tubing_od, tubing_id, available_compression, result):
    """Save completion data and reflect feasibility on the related trend record."""
    completion, _ = CompletionData.objects.update_or_create(
        analysis=analysis,
        well_id=well_id,
        defaults={
            'mandrel_depths': mandrel_depths,
            'packer_depth': packer_depth,
            'tubing_od': tubing_od,
            'tubing_id': tubing_id,
            'injection_pressure_required': result.get('required_pressure_at_deepest'),
            'feasibility_flag': 'feasible' if result.get('overall_feasible') else 'pressure_limited',
        }
    )

    well_trend = WellTrendAnalysis.objects.filter(analysis=analysis, well_id=well_id).first()
    if well_trend:
        if result.get('overall_feasible'):
            well_trend.completion_feasibility = 'feasible'
        else:
            deficits = [item.get('deficit_psi', 0) for item in (result.get('mandrel_analysis') or []) if isinstance(item, dict)]
            deficit = max(deficits, default=0)
            well_trend.completion_feasibility = 'pressure_limited' if deficit < 200 else 'requires_deepening'
        well_trend.save(update_fields=['completion_feasibility'])

    return completion


@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def upload_completion_data(request, analysis_id):
    """Upload completion data for feasibility check - Step 4b"""
    analysis = get_object_or_404(AnalysisSession, id=analysis_id, user=request.user)
    existing_completions = CompletionData.objects.filter(analysis=analysis).order_by('well_id')
    wells = []
    try:
        col_mapping = ColumnMapping.objects.get(upload=analysis.upload)
        rows = _load_data(analysis.upload, col_mapping.mapping)
        wells = _unique_wells(rows)
    except ColumnMapping.DoesNotExist:
        wells = []
    except Exception:
        wells = []
    
    if request.method == 'POST':
        # Priority: uploaded file -> raw CSV body -> JSON body -> form submission
        # 1) Uploaded file
        if request.FILES.get('completion_file'):
            completion_file = request.FILES.get('completion_file')
            # Wrap file as text
            try:
                text_file = io.TextIOWrapper(completion_file.file, encoding='utf-8', newline='')
            except Exception:
                try:
                    completion_file.seek(0)
                except Exception:
                    pass
                text_file = io.TextIOWrapper(completion_file, encoding='utf-8', newline='')

            reader = csv.DictReader(text_file)
            processed = 0
            errors = []
            for i, row in enumerate(reader, start=1):
                try:
                    well_id = (row.get('well_id') or row.get('well') or '').strip()
                    if not well_id:
                        raise ValueError('Missing well_id')

                    mandrel_str = row.get('mandrel_depths', '')
                    mandrel_depths = [float(p.strip()) for p in mandrel_str.split(',') if p.strip()]

                    packer_depth = float(row.get('packer_depth')) if row.get('packer_depth') else None
                    tubing_od = float(row.get('tubing_od')) if row.get('tubing_od') else None
                    tubing_id = float(row.get('tubing_id')) if row.get('tubing_id') else None
                    available_compression = float(row.get('available_compression_pressure')) if row.get('available_compression_pressure') else None

                    result = CompletionFeasibilityChecker.analyze_completion(
                        mandrel_depths=mandrel_depths,
                        packer_depth_ft=packer_depth,
                        tubing_id_inch=tubing_id,
                        available_compression_pressure_psi=available_compression
                    )

                    _persist_completion_record(
                        analysis=analysis,
                        well_id=well_id,
                        mandrel_depths=mandrel_depths,
                        packer_depth=packer_depth,
                        tubing_od=tubing_od,
                        tubing_id=tubing_id,
                        available_compression=available_compression,
                        result=result,
                    )

                    processed += 1
                except Exception as e:
                    errors.append(f'Row {i}: {str(e)}')
            try:
                text_file.detach()
            except Exception:
                pass

            # Return JSON for API clients
            if (request.headers.get('Accept') == 'application/json'
                or request.content_type == 'application/json'
                or request.headers.get('x-requested-with') == 'XMLHttpRequest'):
                return JsonResponse({'processed': processed, 'errors': errors})

            msg = f'Processed {processed} completion record(s).'
            if errors:
                messages.warning(request, msg + ' Some rows had errors: ' + '; '.join(errors[:5]))
            else:
                messages.success(request, msg)
            return redirect('analysis:well_trends', analysis_id=analysis.id)

        # 2) Raw CSV body
        if request.content_type and 'csv' in request.content_type:
            try:
                body_text = request.body.decode('utf-8')
                reader = csv.DictReader(io.StringIO(body_text))
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

            processed = 0
            errors = []
            for i, row in enumerate(reader, start=1):
                try:
                    well_id = (row.get('well_id') or row.get('well') or '').strip()
                    if not well_id:
                        raise ValueError('Missing well_id')
                    mandrel_str = row.get('mandrel_depths', '')
                    mandrel_depths = [float(p.strip()) for p in mandrel_str.split(',') if p.strip()]
                    packer_depth = float(row.get('packer_depth')) if row.get('packer_depth') else None
                    tubing_od = float(row.get('tubing_od')) if row.get('tubing_od') else None
                    tubing_id = float(row.get('tubing_id')) if row.get('tubing_id') else None
                    available_compression = float(row.get('available_compression_pressure')) if row.get('available_compression_pressure') else None

                    result = CompletionFeasibilityChecker.analyze_completion(
                        mandrel_depths=mandrel_depths,
                        packer_depth_ft=packer_depth,
                        tubing_id_inch=tubing_id,
                        available_compression_pressure_psi=available_compression
                    )

                    _persist_completion_record(
                        analysis=analysis,
                        well_id=well_id,
                        mandrel_depths=mandrel_depths,
                        packer_depth=packer_depth,
                        tubing_od=tubing_od,
                        tubing_id=tubing_id,
                        available_compression=available_compression,
                        result=result,
                    )
                    processed += 1
                except Exception as e:
                    errors.append(f'Row {i}: {str(e)}')

            return JsonResponse({'processed': processed, 'errors': errors})

        # 3) JSON body
        if request.content_type and 'json' in request.content_type:
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except Exception as e:
                return JsonResponse({'error': f'Invalid JSON body: {e}'}, status=400)

            records = payload if isinstance(payload, list) else [payload]
            processed = 0
            errors = []
            for i, rec in enumerate(records, start=1):
                try:
                    well_id = (rec.get('well_id') or rec.get('well') or '').strip()
                    if not well_id:
                        raise ValueError('Missing well_id')
                    mandrel_depths = rec.get('mandrel_depths') or []
                    if isinstance(mandrel_depths, str):
                        mandrel_depths = [float(p.strip()) for p in mandrel_depths.split(',') if p.strip()]
                    packer_depth = float(rec.get('packer_depth')) if rec.get('packer_depth') else None
                    tubing_od = float(rec.get('tubing_od')) if rec.get('tubing_od') else None
                    tubing_id = float(rec.get('tubing_id')) if rec.get('tubing_id') else None
                    available_compression = float(rec.get('available_compression_pressure')) if rec.get('available_compression_pressure') else None

                    result = CompletionFeasibilityChecker.analyze_completion(
                        mandrel_depths=mandrel_depths,
                        packer_depth_ft=packer_depth,
                        tubing_id_inch=tubing_id,
                        available_compression_pressure_psi=available_compression
                    )

                    _persist_completion_record(
                        analysis=analysis,
                        well_id=well_id,
                        mandrel_depths=mandrel_depths,
                        packer_depth=packer_depth,
                        tubing_od=tubing_od,
                        tubing_id=tubing_id,
                        available_compression=available_compression,
                        result=result,
                    )
                    processed += 1
                except Exception as e:
                    errors.append(f'Record {i}: {str(e)}')

            return JsonResponse({'processed': processed, 'errors': errors})

        # 4) Fallback to form submission
        form = CompletionDataForm(request.POST)
        if form.is_valid():
            well_id = form.cleaned_data['well_id']
            mandrel_depths = form.cleaned_data['mandrel_depths']
            packer_depth = form.cleaned_data['packer_depth']
            tubing_od = form.cleaned_data.get('tubing_od')
            tubing_id = form.cleaned_data.get('tubing_id')
            available_compression = form.cleaned_data['available_compression_pressure']

            # Run feasibility analysis
            result = CompletionFeasibilityChecker.analyze_completion(
                mandrel_depths=mandrel_depths,
                packer_depth_ft=packer_depth,
                tubing_id_inch=tubing_id,
                available_compression_pressure_psi=available_compression
            )

            _persist_completion_record(
                analysis=analysis,
                well_id=well_id,
                mandrel_depths=mandrel_depths,
                packer_depth=packer_depth,
                tubing_od=tubing_od,
                tubing_id=tubing_id,
                available_compression=available_compression,
                result=result,
            )

            messages.success(request, f'Completion data saved for {well_id}. {result.get("recommendation", "")}')
            return redirect('analysis:well_trends', analysis_id=analysis.id)
    else:
        form = CompletionDataForm()
    
    context = {
        'form': form,
        'analysis': analysis,
        'existing_completions': existing_completions,
        'wells': wells,
    }
    return render(request, 'analysis/upload_completion.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET"])
def run_sensitivity(request, analysis_id):
    """Run Monte Carlo sensitivity analysis"""
    analysis = get_object_or_404(AnalysisSession, id=analysis_id, user=request.user)
    
    try:
        col_mapping = ColumnMapping.objects.get(upload=analysis.upload)
        weights, _ = AnalysisWeights.objects.get_or_create(analysis=analysis)
        rows = _load_data(analysis.upload, col_mapping.mapping)
        
        # Group rows by normalized well id, but keep original display names
        well_data = {}
        well_display = {}
        for r in rows:
            raw_well = r.get('Well')
            well = _normalize_well_id(raw_well)
            if well:
                if well not in well_data:
                    well_data[well] = []
                    well_display[well] = raw_well
                well_data[well].append(r)

        # Honor selected wells if the analysis was scoped (normalize IDs for comparison)
        if analysis.selected_wells:
            normalized_selected = set(_normalize_well_id(w) for w in (analysis.selected_wells or []))
            well_data = {well: rows for well, rows in well_data.items() if well in normalized_selected}
        
        if len(well_data) < 2:
            return JsonResponse({'error': 'Need at least 2 wells for sensitivity analysis'}, status=400)
        
        # Run Monte Carlo simulation with actual analysis settings
        simulator = MonteCarloSensitivity(iterations=1000)
        results = simulator.run_simulation(
            well_data,
            weights,
            base_choke_size=weights.base_choke_size or None,
            outlier_method=getattr(weights, 'outlier_method', 'iqr') or 'iqr',
            outlier_threshold=getattr(weights, 'outlier_threshold', 1.5) or 1.5,
        )
        
        # Classify confidence for each well
        for well_id, data in results.items():
            data['confidence'] = MonteCarloSensitivity.classify_confidence(data['rank_variance'])

        # Map normalized keys back to original display names when possible
        remapped = { (well_display.get(k) or k): v for k, v in results.items() }

        return JsonResponse({'status': 'success', 'results': remapped})
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Sensitivity analysis failed for {analysis.id}: {e}", exc_info=True)
        # Print exception to stdout for test debugging
        try:
            import traceback, sys
            print('SENSITIVITY ERROR:', e, file=sys.stderr)
            traceback.print_exc()
        except Exception:
            pass
        return JsonResponse({'error': str(e)}, status=400)


@login_required(login_url='accounts:login')
@require_http_methods(["GET"])
def compare_analyses(request):
    """Compare two analysis sessions side by side"""
    analysis_id_a = request.GET.get('analysis_a')
    analysis_id_b = request.GET.get('analysis_b')
    
    if not analysis_id_a or not analysis_id_b:
        analyses = AnalysisSession.objects.filter(user=request.user, status='completed').order_by('-created_at')
        return render(request, 'analysis/compare_analyses.html', {'analyses': analyses})
    
    analysis_a = get_object_or_404(AnalysisSession, id=analysis_id_a, user=request.user)
    analysis_b = get_object_or_404(AnalysisSession, id=analysis_id_b, user=request.user)
    
    trends_a = {_normalize_well_id(t.well_id): t for t in WellTrendAnalysis.objects.filter(analysis=analysis_a)}
    trends_b = {_normalize_well_id(t.well_id): t for t in WellTrendAnalysis.objects.filter(analysis=analysis_b)}
    
    # Build delta table
    all_wells = set(list(trends_a.keys()) + list(trends_b.keys()))
    deltas = []
    for well_id in sorted(all_wells):
        t_a = trends_a.get(well_id)
        t_b = trends_b.get(well_id)

        delta = {
            'well_id': well_id,
            'rank_a': t_a.rank if t_a else None,
            'rank_b': t_b.rank if t_b else None,
            'score_a': t_a.candidate_score if t_a else None,
            'score_b': t_b.candidate_score if t_b else None,
        }

        if delta['rank_a'] is not None and delta['rank_b'] is not None:
            delta['rank_change'] = delta['rank_a'] - delta['rank_b']
            delta['improved'] = delta['rank_change'] > 0
            delta['deteriorated'] = delta['rank_change'] < 0
            delta['new_well'] = False
            delta['removed_well'] = False
        else:
            delta['rank_change'] = None
            delta['improved'] = False
            delta['deteriorated'] = False
            delta['new_well'] = delta['rank_a'] is None and delta['rank_b'] is not None
            delta['removed_well'] = delta['rank_a'] is not None and delta['rank_b'] is None

        deltas.append(delta)

    def _compare_sort_key(item):
        if item.get('rank_change') is not None:
            return (2, abs(item['rank_change']), item['rank_b'] or 0)
        if item.get('new_well'):
            return (1, 0, item['rank_b'] or 0)
        if item.get('removed_well'):
            return (0, 0, item['rank_a'] or 0)
        return (-1, 0, 0)

    deltas.sort(key=_compare_sort_key, reverse=True)

    context = {
        'analysis_a': analysis_a,
        'analysis_b': analysis_b,
        'deltas': deltas,
        'summary': {
            'improved': sum(1 for d in deltas if d.get('improved')),
            'deteriorated': sum(1 for d in deltas if d.get('deteriorated')),
            'unchanged': sum(1 for d in deltas if d.get('rank_change') == 0),
            'new_wells': sum(1 for d in deltas if d.get('new_well')),
            'removed_wells': sum(1 for d in deltas if d.get('removed_well')),
        }
    }
    
    return render(request, 'analysis/compare_results.html', context)


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


def _normalize_well_id(well_id):
    if well_id is None:
        return None
    if isinstance(well_id, str):
        normalized = re.sub(r'[^a-z0-9]+', '', well_id.lower())
        return normalized.strip()
    return re.sub(r'[^a-z0-9]+', '', str(well_id).lower()).strip()


def _load_data(upload, mapping):
    """Helper to load and map data from upload. Returns list of dicts."""
    rows = DataProcessor.read_file(upload.file, upload.file_format)

    if not rows:
        return []

    # Rename columns
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

    # Convert date strings to datetime objects
    for row in mapped_rows:
        if row.get('Date') is not None and row['Date'] != '':
            try:
                row['Date'] = _parse_date(row['Date'])
            except (ValueError, TypeError):
                row['Date'] = None
        else:
            row['Date'] = None

    # Convert numeric columns
    numeric_cols = [
        'BS&W (%)',
        'Net Oil (bopd)',
        'Form.GLR (scf/bbl)',
        'Tubing Pressure (psi)',
        'Flow Line Pressure (psi)',
        'Reservoir Pressure (psi)',
        'Flowing BHP (psi)',
    ]
    for col in numeric_cols:
        for row in mapped_rows:
            if col in row:
                val = row[col]
                if val is not None and val != '':
                    row[col] = _coerce_numeric(val)
                else:
                    row[col] = None

    return mapped_rows


def _safe_series_to_list(series):
    """Convert a list of values to a JSON-safe list, keeping None for nulls."""
    return [x if x is not None else None for x in series]


def _normalize_chart_series(values, expected_length=None):
    """Convert chart values to JSON-safe numbers and align them to the expected length."""
    if values is None:
        return []

    normalized = []
    for value in values:
        if value is None or value == '':
            normalized.append(None)
            continue
        try:
            normalized.append(float(value))
        except (TypeError, ValueError):
            normalized.append(None)

    if expected_length is None:
        return normalized

    if len(normalized) < expected_length:
        normalized.extend([None] * (expected_length - len(normalized)))
    elif len(normalized) > expected_length:
        normalized = normalized[:expected_length]

    return normalized


def _unique_wells(rows):
    """Get unique well names from data, preserving order."""
    seen = set()
    wells = []
    for r in rows:
        well = _normalize_well_id(r.get('Well'))
        if well is not None and well not in seen and well != '':
            seen.add(well)
            wells.append(well)
    return wells
