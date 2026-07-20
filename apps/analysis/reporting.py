
"""
PDF Report generation for executive summaries.
"""
import io
import os
from datetime import datetime
from django.conf import settings
from django.db.models import Avg, Min, Max, Count, Sum
from apps.analysis.models import WellTrendAnalysis


class ReportGenerator:
    """Generate executive summary PDF reports"""
    
    @staticmethod
    def generate_bubble_chart_html(well_trends):
        """
        Generate HTML for an Oil Rate vs BSW bubble chart.
        Returns HTML with embedded Chart.js configuration.
        """
        chart_data = []
        for trend in well_trends[:30]:  # Limit to 30 wells
            chart_data.append({
                'well_id': trend.well_id,
                'oil_rate': trend.candidate_score or 0,
                'bsw_flag': 1 if trend.bsw_flag else 0,
                'rank': trend.rank or 0,
                'liquid_loading': 1 if trend.liquid_loading_flag else 0,
            })
        
        import json
        return f"""
        <div style="width: 100%; max-width: 700px; margin: 20px auto;">
            <canvas id="reportBubbleChart" width="700" height="400"></canvas>
        </div>
        <script>
        const bubbleData = {json.dumps(chart_data)};
        </script>
        """
    
    @staticmethod
    def _feasibility_label(value):
        """Convert feasibility value to display label."""
        mapping = {
            'feasible': 'Feasible',
            'requires_deepening': 'Requires Tubing Deepening',
            'pressure_limited': 'Insufficient Injection Pressure',
            'unknown': 'Unknown',
        }
        return mapping.get(value, 'Unknown')
    
    @staticmethod
    def _trend_arrow(value, magnitude=None):
        """Return trend arrow symbol."""
        if value == 'increasing':
            return '&#8593;'  # up arrow
        elif value == 'decreasing':
            return '&#8595;'  # down arrow
        return '&#8594;'  # right arrow
    
    @staticmethod
    def _trend_color(value, adverse=False):
        """Return color for trend."""
        if value == 'increasing':
            return '#e74c3c' if adverse else '#27ae60'
        elif value == 'decreasing':
            return '#27ae60' if adverse else '#e74c3c'
        return '#666'

    @staticmethod
    def _format_pct(value, total):
        if not total:
            return '0%'
        return f"{value / total * 100:.0f}%"

    @staticmethod
    def _format_num(value, precision=1):
        if value is None:
            return 'N/A'
        if isinstance(value, int):
            return str(value)
        return f"{value:.{precision}f}"
    
    @staticmethod
    def generate_executive_html(analysis, well_trends, completion_data=None):
        """
        Generate executive summary HTML for PDF conversion.
        
        Parameters:
            analysis: AnalysisSession instance
            well_trends: QuerySet of WellTrendAnalysis ordered by rank
            completion_data: Optional dict of well_id -> CompletionData
        
        Returns:
            Complete HTML document string
        """
        top5 = well_trends.filter(rank__lte=5)
        total_wells = well_trends.count()
        
        # Summary statistics
        avg_score = well_trends.aggregate(Avg('candidate_score'))['candidate_score__avg'] or 0
        max_score = well_trends.aggregate(Max('candidate_score'))['candidate_score__max'] or 0
        liquid_loaded = well_trends.filter(liquid_loading_flag=True).count()
        declining_oil = well_trends.filter(oil_rate_flag=True).count()
        increasing_bsw = well_trends.filter(bsw_flag=True).count()
        declining_glr = well_trends.filter(glr_flag=True).count()
        
        # Wells with both declining oil and high BSW (critical)
        critical_wells = well_trends.filter(oil_rate_flag=True, bsw_flag=True).count()
        
        # Economic summary
        wells_with_days = well_trends.exclude(days_to_economic_limit__isnull=True)
        urgent = wells_with_days.filter(days_to_economic_limit__lte=90).count()
        near_term = wells_with_days.filter(days_to_economic_limit__gt=90, days_to_economic_limit__lte=180).count()
        
        wells_with_pi = well_trends.exclude(productivity_index__isnull=True)
        avg_pi = wells_with_pi.aggregate(Avg('productivity_index'))['productivity_index__avg'] or 0

        # Data quality summary
        good_data = well_trends.filter(data_quality_score__gte=80).count()
        poor_data = well_trends.filter(data_quality_score__lt=60).count()
        
        # Feasibility breakdown
        feasibility_counts = well_trends.values('completion_feasibility').annotate(count=Count('id'))
        feas_map = {f['completion_feasibility']: f['count'] for f in feasibility_counts}
        feas_feasible = feas_map.get('feasible', 0)
        feas_deepen = feas_map.get('requires_deepening', 0)
        feas_pressure = feas_map.get('pressure_limited', 0)
        
        # Gas allocation stats
        wells_with_gas = well_trends.exclude(recommended_gas_mmscf__isnull=True)
        total_gas = wells_with_gas.aggregate(Sum('recommended_gas_mmscf'))['recommended_gas_mmscf__sum'] or 0
        avg_gas = wells_with_gas.aggregate(Avg('recommended_gas_mmscf'))['recommended_gas_mmscf__avg'] or 0
        
        # Score distribution
        high_score = well_trends.filter(candidate_score__gte=25).count()
        medium_score = well_trends.filter(candidate_score__gte=15, candidate_score__lt=25).count()
        low_score = well_trends.filter(candidate_score__lt=15).count()
        
        # Urgency categories
        stable = max(0, total_wells - urgent - near_term)
        
        # Narrative summary
        summary_lines = [
            f"Analyzed {total_wells} well(s) from {analysis.upload.filename}.",
            f"Average candidate score is {avg_score:.1f}, with {high_score} high-priority candidate(s).",
        ]
        if critical_wells > 0:
            summary_lines.append(f"{critical_wells} well(s) show both declining oil rate and rising BSW, indicating top intervention priority.")
        if urgent > 0:
            summary_lines.append(f"{urgent} well(s) are within 90 days of economic limit.")
        if liquid_loaded > 0:
            summary_lines.append(f"{liquid_loaded} well(s) show liquid loading risk and could benefit from gas lift intervention.")
        if total_gas > 0:
            summary_lines.append(f"Total recommended lift gas for the portfolio is {total_gas:.1f} MMscf/d.")
        summary_text = ' '.join(summary_lines)
        
        top5_wells = [trend.well_id for trend in top5]
        top5_label = ', '.join(top5_wells) if top5_wells else 'N/A'
        
        # ROM CAPEX estimates
        rom_capex = 500000  # $500k per well (typical)
        total_recommended = top5.count()
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Gas Lift Candidate Executive Summary</title>
    <style>
        body {{ font-family: Arial, Helvetica, sans-serif; margin: 40px; color: #333; font-size: 11px; }}
        h1 {{ color: #1a5276; border-bottom: 3px solid #2980b9; padding-bottom: 10px; font-size: 22px; }}
        h2 {{ color: #2c3e50; margin-top: 25px; font-size: 15px; border-bottom: 1px solid #ddd; padding-bottom: 6px; }}
        h3 {{ color: #34495e; font-size: 13px; margin: 15px 0 8px 0; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ border: none; font-size: 24px; }}
        .header p {{ font-size: 11px; color: #666; margin: 3px 0; }}
        .summary-box {{ background: #f0f4f8; border: 1px solid #d0dbe8; border-radius: 8px; padding: 15px; margin: 15px 0; }}
        .summary-box table {{ width: 100%; table-layout: fixed; border-collapse: collapse; }}
        .summary-box td {{ padding: 10px 6px; text-align: center; width: 20%; vertical-align: top; }}
        .summary-text {{ background: #ffffff; border: 1px solid #d5dbe8; border-radius: 8px; padding: 15px; margin: 15px 0; }}
        .summary-text h2 {{ margin-top: 0; }}
        .summary-text p {{ margin: 0 0 10px 0; line-height: 1.5; color: #444; }}
        .summary-text ul {{ margin: 0; padding-left: 18px; color: #444; }}
        .metric-grid {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 15px; }}
        .metric-card {{ flex: 1 1 calc(33.333% - 12px); background: #ffffff; border: 1px solid #d5dbe8; border-radius: 8px; padding: 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); min-width: 150px; }}
        .metric-card .value {{ font-size: 24px; font-weight: bold; color: #1a5276; margin-bottom: 6px; }}
        .metric-card .label {{ font-size: 10px; color: #666; text-transform: uppercase; letter-spacing: 0.05em; }}
        .stat {{ font-size: 26px; font-weight: bold; color: #1a5276; display: block; white-space: nowrap; }}
        .stat-label {{ font-size: 10px; color: #555; display: block; padding-top: 2px; }}
        .stat-sub {{ font-size: 11px; color: #888; display: block; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th {{ background: #1a5276; color: white; padding: 5px 6px; text-align: left; font-size: 10px; white-space: nowrap; }}
        td {{ padding: 5px 6px; border-bottom: 1px solid #e0e0e0; font-size: 10px; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .footer {{ margin-top: 40px; font-size: 9px; color: #999; text-align: center; border-top: 1px solid #ddd; padding-top: 15px; }}
        .footer p {{ margin: 2px 0; }}
        
        .badge {{ display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 9px; white-space: nowrap; font-weight: bold; }}
        .badge-danger {{ background: #e74c3c; color: white; }}
        .badge-success {{ background: #27ae60; color: white; }}
        .badge-warning {{ background: #f39c12; color: white; }}
        .badge-info {{ background: #3498db; color: white; }}
        .badge-secondary {{ background: #95a5a6; color: white; }}
        
        .flag-up {{ color: #27ae60; font-size: 14px; }}
        .flag-down {{ color: #e74c3c; font-size: 14px; }}
        .flag-flat {{ color: #666; font-size: 14px; }}
        
        /* Well cards for top 5 */
        .well-card {{ background: #fff; border: 1px solid #d5dbe8; border-radius: 6px; padding: 12px; margin: 12px 0; page-break-inside: avoid; }}
        .well-card h3 {{ margin: 0 0 8px 0; font-size: 14px; color: #1a5276; }}
        .well-card .meta {{ font-size: 10px; color: #888; margin-bottom: 8px; }}
        .well-card .metrics {{ width: 100%; }}
        .well-card .metrics td {{ padding: 4px 8px; font-size: 10px; border: none; vertical-align: top; }}
        .well-card .metrics th {{ background: transparent; color: #555; padding: 4px 8px; font-size: 9px; border-bottom: 1px solid #ddd; text-align: left; white-space: nowrap; }}
        .well-card .section-label {{ font-weight: bold; color: #2c3e50; font-size: 10px; padding-top: 8px !important; border-top: 1px solid #eee; }}
        
        /* Two-column layout */
        .row {{ width: 100%; }}
        .col-left {{ float: left; width: 48%; }}
        .col-right {{ float: right; width: 48%; }}
        .clear {{ clear: both; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Gas Lift Candidate Executive Summary</h1>
        <p>Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}</p>
        <p>Dataset: <strong>{analysis.upload.filename}</strong> | Wells Analyzed: <strong>{total_wells}</strong></p>
    </div>

    <div class="summary-text">
        <h2>Executive Summary</h2>
        <p>{summary_text}</p>
        <ul>
            <li>Top 5 candidates: {top5_label}</li>
            <li>Average recommended gas per candidate: {avg_gas:.2f} MMscf/d</li>
            <li>Data quality: {good_data} wells ≥80% good data, {poor_data} wells <60% good data</li>
        </ul>
    </div>

    <div class="metric-grid">
        <div class="metric-card">
            <div class="value">{total_wells}</div>
            <div class="label">Wells Analyzed</div>
        </div>
        <div class="metric-card">
            <div class="value">{avg_score:.1f}</div>
            <div class="label">Average Candidate Score</div>
        </div>
        <div class="metric-card">
            <div class="value">{high_score}</div>
            <div class="label">High Score Opportunities</div>
        </div>
        <div class="metric-card">
            <div class="value">{urgent}</div>
            <div class="label">Urgent Wells (≤90d)</div>
        </div>
        <div class="metric-card">
            <div class="value">{total_gas:.1f}</div>
            <div class="label">Total Rec. Gas (MMscf/d)</div>
        </div>
        <div class="metric-card">
            <div class="value">{avg_pi:.2f}</div>
            <div class="label">Average Productivity Index</div>
        </div>
    </div>

    <!-- ===== FLAG BREAKDOWN ===== -->
    <div class="row">
        <div class="col-left">
            <h3>Alert Flags</h3>
            <table>
                <tr><th>Flag Type</th><th>Wells</th><th>% of Total</th></tr>
                <tr><td>Rising BSW</td><td>{increasing_bsw}</td><td>{increasing_bsw/total_wells*100:.0f}%</td></tr>
                <tr><td>Declining Oil Rate</td><td>{declining_oil}</td><td>{declining_oil/total_wells*100:.0f}%</td></tr>
                <tr><td>Declining GLR</td><td>{declining_glr}</td><td>{declining_glr/total_wells*100:.0f}%</td></tr>
                <tr><td>Liquid Loading</td><td>{liquid_loaded}</td><td>{liquid_loaded/total_wells*100:.0f}%</td></tr>
                <tr><td><strong>Critical (Oil & BSW)</strong></td><td><strong>{critical_wells}</strong></td><td><strong>{critical_wells/total_wells*100:.0f}%</strong></td></tr>
            </table>
        </div>
        <div class="col-right">
            <h3>Candidate Score Distribution</h3>
            <table>
                <tr><th>Category</th><th>Wells</th><th>% of Total</th></tr>
                <tr><td><span class="badge badge-success">High</span> (>=25)</td><td>{high_score}</td><td>{high_score/total_wells*100:.0f}%</td></tr>
                <tr><td><span class="badge badge-warning">Medium</span> (15-25)</td><td>{medium_score}</td><td>{medium_score/total_wells*100:.0f}%</td></tr>
                <tr><td><span class="badge badge-secondary">Low</span> (<15)</td><td>{low_score}</td><td>{low_score/total_wells*100:.0f}%</td></tr>
            </table>
        </div>
    </div>
    <div class="clear"></div>

    <!-- ===== COMPLETION FEASIBILITY ===== -->
    <div class="row">
        <div class="col-left">
            <h3>Completion Feasibility</h3>
            <table>
                <tr><th>Status</th><th>Wells</th><th>% of Total</th></tr>
                <tr><td><span class="badge badge-success">Feasible</span></td><td>{feas_feasible}</td><td>{feas_feasible/total_wells*100:.0f}%</td></tr>
                <tr><td><span class="badge badge-warning">Needs Deepening</span></td><td>{feas_deepen}</td><td>{feas_deepen/total_wells*100:.0f}%</td></tr>
                <tr><td><span class="badge badge-danger">Pressure Limited</span></td><td>{feas_pressure}</td><td>{feas_pressure/total_wells*100:.0f}%</td></tr>
            </table>
        </div>
        <div class="col-right">
            <h3>Economic Urgency</h3>
            <table>
                <tr><th>Days to Economic Limit</th><th>Wells</th><th>% of Total</th></tr>
                <tr><td><span class="badge badge-danger">Urgent</span> (&le;90 days)</td><td>{urgent}</td><td>{urgent/total_wells*100:.0f}%</td></tr>
                <tr><td><span class="badge badge-warning">Near-term</span> (91-180 days)</td><td>{near_term}</td><td>{near_term/total_wells*100:.0f}%</td></tr>
                <tr><td><span class="badge badge-success">Stable</span> (>180 days)</td><td>{wells_with_days.count() - urgent - near_term}</td><td>{(wells_with_days.count() - urgent - near_term)/total_wells*100:.0f}%</td></tr>
                <tr><td><span class="badge badge-secondary">No data</span></td><td>{total_wells - wells_with_days.count()}</td><td>{(total_wells - wells_with_days.count())/total_wells*100:.0f}%</td></tr>
            </table>
        </div>
    </div>
    <div class="clear"></div>

    <!-- ===== RESERVOIR INSIGHTS ===== -->
    <h3>Reservoir & Production Insights</h3>
    <div class="summary-box" style="padding: 10px 15px;">
        <table>
            <tr>
                <td><span class="stat">{avg_pi:.2f}</span><span class="stat-label">Avg PI (bopd/psi)</span></td>
                <td><span class="stat">{liquid_loaded}</span><span class="stat-label">Liquid Loaded Wells</span></td>
                <td><span class="stat">{declining_oil}</span><span class="stat-label">Declining Oil Rate Wells</span></td>
                <td><span class="stat">{increasing_bsw}</span><span class="stat-label">Rising BSW Wells</span></td>
                <td><span class="stat">{declining_glr}</span><span class="stat-label">Declining GLR Wells</span></td>
            </tr>
            <tr>
                <td colspan="2"><span class="stat">{good_data}</span><span class="stat-label">High Quality Data Wells</span></td>
                <td colspan="3"><span class="stat">{poor_data}</span><span class="stat-label">Lower Quality Data Wells</span></td>
            </tr>
        </table>
    </div>

    <!-- ===== TOP 5 DETAILED WELL CARDS ===== -->
    <h2>Top 5 Recommended Candidates — Detailed Analysis</h2>
"""
        for trend in top5:
            # Determine trend colors for adverse indicators
            bsw_arrow = ReportGenerator._trend_arrow(trend.bsw_trend)
            oil_arrow = ReportGenerator._trend_arrow(trend.oil_rate_trend)
            glr_arrow = ReportGenerator._trend_arrow(trend.glr_trend)
            tp_arrow = ReportGenerator._trend_arrow(trend.tubing_pressure_trend)
            pi_arrow = ReportGenerator._trend_arrow(trend.pi_trend)
            
            bsw_color = ReportGenerator._trend_color(trend.bsw_trend, adverse=True)
            oil_color = ReportGenerator._trend_color(trend.oil_rate_trend, adverse=False)
            glr_color = ReportGenerator._trend_color(trend.glr_trend, adverse=False)
            
            feasibility_label = ReportGenerator._feasibility_label(trend.completion_feasibility)
            
            # Completion data
            completion = completion_data.get(trend.well_id) if completion_data else None
            injection_pressure = completion.injection_pressure_required if completion else None
            packer_depth = completion.packer_depth if completion else None
            
            liquid_loading_badge = '<span class="badge badge-danger">Yes</span>' if trend.liquid_loading_flag else '<span class="badge badge-success">No</span>'
            
            # Score color badge
            if trend.candidate_score >= 25:
                score_badge = 'badge-success'
            elif trend.candidate_score >= 15:
                score_badge = 'badge-warning'
            else:
                score_badge = 'badge-secondary'
            
            html += f"""
    <div class="well-card">
        <h3>#{trend.rank} — {trend.well_id}  <span class="badge {score_badge}" style="font-size:11px; padding:3px 10px;">Score: {trend.candidate_score:.0f}</span></h3>
        <div class="meta">
            Prod Method: {trend.prod_method or 'N/A'} | 
            Choke: {trend.well_choke_size or 'N/A'} | 
            Data Quality: {trend.data_quality_score:.0f}% | 
            Outliers Removed: {trend.outlier_count}
        </div>
        <table class="metrics">
            <tr>
                <th style="width: 14%;">Parameter</th>
                <th style="width: 12%;">Trend</th>
                <th style="width: 12%;">Slope</th>
                <th style="width: 12%;">Magnitude</th>
                <th style="width: 14%;">Flag</th>
                <th style="width: 14%;">Current Value</th>
                <th style="width: 22%;">Diagnostic</th>
            </tr>
            <tr>
                <td>BSW</td>
                <td style="color:{bsw_color};">{bsw_arrow} {trend.bsw_trend or 'no trend'}</td>
                <td>{f'{trend.bsw_slope:.4f}' if trend.bsw_slope else 'N/A'}</td>
                <td>{trend.bsw_magnitude or 'N/A'}</td>
                <td>{'<span class="badge badge-danger">Flagged</span>' if trend.bsw_flag else '<span class="badge badge-success">OK</span>'}</td>
                <td>--</td>
                <td><small>Water cut is {'rising' if trend.bsw_flag else 'stable'}.</small></td>
            </tr>
            <tr>
                <td>Oil Rate</td>
                <td style="color:{oil_color};">{oil_arrow} {trend.oil_rate_trend or 'no trend'}</td>
                <td>{f'{trend.oil_rate_slope:.4f}' if trend.oil_rate_slope else 'N/A'}</td>
                <td>{trend.oil_rate_magnitude or 'N/A'}</td>
                <td>{'<span class="badge badge-danger">Flagged</span>' if trend.oil_rate_flag else '<span class="badge badge-success">OK</span>'}</td>
                <td>6mo proj: {f'{trend.projected_oil_rate_6mo:.0f}' if trend.projected_oil_rate_6mo is not None else 'N/A'} bopd</td>
                <td><small>Oil production {'declining' if trend.oil_rate_flag else 'stable'}.</small></td>
            </tr>
            <tr>
                <td>GLR</td>
                <td style="color:{glr_color};">{glr_arrow} {trend.glr_trend or 'no trend'}</td>
                <td>{f'{trend.glr_slope:.4f}' if trend.glr_slope else 'N/A'}</td>
                <td>{trend.glr_magnitude or 'N/A'}</td>
                <td>{'<span class="badge badge-danger">Flagged</span>' if trend.glr_flag else '<span class="badge badge-success">OK</span>'}</td>
                <td>Crit GLR: {f'{trend.critical_glr:.0f}' if trend.critical_glr else 'N/A'} scf/bbl<br>Actual: {f'{trend.actual_glr:.0f}' if trend.actual_glr else 'N/A'} scf/bbl</td>
                <td><small>GLR {'declining, may indicate lift gas depletion.' if trend.glr_flag else 'is stable.'}</small></td>
            </tr>
            <tr>
                <td>Tubing Pressure</td>
                <td>{tp_arrow} {trend.tubing_pressure_trend or 'no trend'}</td>
                <td>{f'{trend.tubing_pressure_slope:.4f}' if trend.tubing_pressure_slope else 'N/A'}</td>
                <td>{trend.tubing_pressure_magnitude or 'N/A'}</td>
                <td>--</td>
                <td>--</td>
                <td><small>Tubing pressure {'declining' if trend.tubing_pressure_trend == 'decreasing' else ('rising' if trend.tubing_pressure_trend == 'increasing' else 'stable')}.</small></td>
            </tr>
            <tr><td colspan="7" class="section-label">Liquid Loading Diagnostics</td></tr>
            <tr>
                <td colspan="2">Liquid Loading:</td>
                <td colspan="2">{liquid_loading_badge}</td>
                <td colspan="2">Crit Vel: {f'{trend.critical_velocity:.1f}' if trend.critical_velocity else 'N/A'} ft/s<br>Act Vel: {f'{trend.actual_velocity:.1f}' if trend.actual_velocity else 'N/A'} ft/s</td>
                <td><small>{'Well is liquid-loaded, gas lift recommended.' if trend.liquid_loading_flag else 'No liquid loading issues detected.'}</small></td>
            </tr>
            <tr><td colspan="7" class="section-label">Reservoir & Completion</td></tr>
            <tr>
                <td colspan="2">PI: {f'{trend.productivity_index:.2f}' if trend.productivity_index else 'N/A'} bopd/psi</td>
                <td colspan="2">PI Trend: {pi_arrow} {trend.pi_trend or 'N/A'}</td>
                <td colspan="2">Feasibility: {feasibility_label}</td>
                <td><small>{'Completion feasible for gas lift.' if trend.completion_feasibility == 'feasible' else ('Tubing deepening may be required.' if trend.completion_feasibility == 'requires_deepening' else ('Injection pressure insufficient.' if trend.completion_feasibility == 'pressure_limited' else 'Feasibility not assessed.'))}</small></td>
            </tr>
            <tr><td colspan="7" class="section-label">Economics & Gas Allocation</td></tr>
            <tr>
                <td colspan="2">Days to Econ Limit: <strong>{trend.days_to_economic_limit if trend.days_to_economic_limit else 'N/A'}</strong></td>
                <td colspan="2">Projected 6mo: {f'{trend.projected_oil_rate_6mo:.1f}' if trend.projected_oil_rate_6mo else 'N/A'} bopd</td>
                <td colspan="2">Rec. Gas: {f'{trend.recommended_gas_mmscf:.2f}' if trend.recommended_gas_mmscf else 'N/A'} MMscf/d<br>Util Eff: {f'{trend.gas_utilization_efficiency:.0f}' if trend.gas_utilization_efficiency else 'N/A'}%</td>
                <td><small>{trend.summary_comment}</small></td>
            </tr>
        </table>
    </div>
"""

        # ===== ALL CANDIDATES TABLE =====
        html += """
    <h2>All Candidate Rankings</h2>
    <table>
        <tr>
            <th>Rank</th>
            <th>Well</th>
            <th>Score</th>
            <th>BSW</th>
            <th>Oil</th>
            <th>GLR</th>
            <th>Liq Load</th>
            <th>Days to Limit</th>
            <th>Feasibility</th>
            <th>Rec. Gas (MMscf/d)</th>
        </tr>
"""
        for trend in well_trends[:50]:
            feasibility_display = ReportGenerator._feasibility_label(trend.completion_feasibility) if trend.completion_feasibility else 'N/A'
            
            bsw_badge = '<span class="badge badge-danger">Yes</span>' if trend.bsw_flag else 'No'
            oil_badge = '<span class="badge badge-danger">Yes</span>' if trend.oil_rate_flag else 'No'
            glr_badge = '<span class="badge badge-danger">Yes</span>' if trend.glr_flag else 'No'
            ll_badge = '<span class="badge badge-warning">Yes</span>' if trend.liquid_loading_flag else 'No'
            
            html += f"""
        <tr>
            <td>#{trend.rank}</td>
            <td><strong>{trend.well_id}</strong></td>
            <td>{trend.candidate_score:.0f}</td>
            <td>{bsw_badge}</td>
            <td>{oil_badge}</td>
            <td>{glr_badge}</td>
            <td>{ll_badge}</td>
            <td>{trend.days_to_economic_limit if trend.days_to_economic_limit else 'N/A'}</td>
            <td>{feasibility_display}</td>
            <td>{f'{trend.recommended_gas_mmscf:.2f}' if trend.recommended_gas_mmscf else 'N/A'}</td>
        </tr>
"""

        # ===== KEY OBSERVATIONS =====
        html += """
    </table>

    <h2>Key Observations & Recommendations</h2>
    <div class="summary-box">
        <table style="width:100%; border: none; table-layout: fixed;">
            <tr>
                <td style="width: 33%; vertical-align: top; text-align: left; border: none;">
                    <strong>Production Trends</strong><br>
                    <small>
"""
        if critical_wells > 0:
            html += f"""
                    - {critical_wells} well(s) show both declining oil AND rising BSW — top intervention priority.<br>
"""
        if declining_oil > 0:
            html += f"""
                    - {declining_oil} well(s) have declining oil rates — candidate for gas lift optimization.<br>
"""
        if increasing_bsw > 0:
            html += f"""
                    - {increasing_bsw} well(s) show rising BSW trend — investigate water shut-off potential.<br>
"""
        html += """
                    </small>
                </td>
                <td style="width: 33%; vertical-align: top; text-align: left; border: none;">
                    <strong>Operational Recommendations</strong><br>
                    <small>
"""
        if liquid_loaded > 0:
            html += f"""
                    - {liquid_loaded} liquid-loaded well(s) identified — gas lift will unload liquids.<br>
"""
        if feas_deepen > 0:
            html += f"""
                    - {feas_deepen} well(s) require tubing deepening — factor into workover cost.<br>
"""
        if feas_pressure > 0:
            html += f"""
                    - {feas_pressure} well(s) have pressure constraints — evaluate compression upgrade.<br>
"""
        html += """
                    </small>
                </td>
                <td style="width: 33%; vertical-align: top; text-align: left; border: none;">
                    <strong>Economic Outlook</strong><br>
                    <small>
"""
        if urgent > 0:
            html += f"""
                    - {urgent} well(s) within 90 days of economic limit — prioritize immediate action.<br>
"""
        if total_gas > 0:
            html += f"""
                    - Total recommended lift gas: {total_gas:.1f} MMscf/d — verify compressor capacity.<br>
"""
        html += f"""
                    - Average candidate score: {avg_score:.1f} (max {max_score:.0f})<br>
                    - Estimated CAPEX for top candidates: ${rom_capex * total_recommended:,}
                    </small>
                </td>
            </tr>
        </table>
    </div>

    <!-- ===== ROM COST ESTIMATE ===== -->
    <h2>Rough Order-of-Magnitude (ROM) Cost Estimate</h2>
    <div class="summary-box">
        <table>
            <tr>
                <td><span class="stat">{total_recommended}</span><span class="stat-label">Top Candidates</span></td>
                <td><span class="stat">${rom_capex * total_recommended:,}</span><span class="stat-label">Est. CAPEX (${rom_capex:,}/well)</span></td>
                <td><span class="stat">$20,000</span><span class="stat-label">Est. OPEX/well/yr</span></td>
                <td><span class="stat">~12-24</span><span class="stat-label">Payback (months)</span></td>
            </tr>
        </table>
        <p style="font-size: 10px; color: #666; margin-top: 8px;">
            <em>Note: ROM estimates are order-of-magnitude only. Accurate budgeting requires detailed well engineering and vendor quotes.</em>
        </p>
    </div>

    <div class="footer">
        <p>Gas Lift Candidate Analysis Platform | Generated from {analysis.upload.filename}</p>
        <p>Report generated {datetime.now().strftime('%B %d, %Y %H:%M')} | {total_wells} wells analyzed</p>
        <p>This report was automatically generated. For the interactive dashboard, visit the Gas Lift Application.</p>
    </div>
</body>
</html>
"""
        return html
    
    @staticmethod
    def generate_pdf(analysis, well_trends, completion_data=None):
        """
        Generate PDF bytes from analysis data.
        
        Returns:
            bytes of PDF content
        """
        html_content = ReportGenerator.generate_executive_html(analysis, well_trends, completion_data)
        
        try:
            import weasyprint
            pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
            return pdf_bytes
        except ImportError:
            # Fallback if weasyprint not installed
            from django.http import HttpResponse
            html_to_pdf = getattr(settings, 'REPORT_HTML_TO_PDF', None)
            if html_to_pdf:
                return html_to_pdf(html_content)
            
            # Return HTML as string if no PDF library available
            return html_content.encode('utf-8')
        except Exception as e:
            # Return HTML on error
            return html_content.encode('utf-8')