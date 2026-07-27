import io
import json
from datetime import datetime
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.test.utils import override_settings

from apps.analysis.completion import CompletionFeasibilityChecker
from apps.analysis.reporting import ReportGenerator
from apps.data_upload.utils import DataProcessor
from apps.analysis.ipr_calculator import LiquidLoadingDiagnostics
from apps.analysis.pvt import PVTProperties
from apps.analysis.sensitivity import MonteCarloSensitivity
from apps.analysis.models import AnalysisSession, CompletionData, WellTrendAnalysis
from apps.data_upload.models import DataUpload, ColumnMapping
from apps.analysis.views import _run_gas_knapsack


class Step4WorkflowTests(TestCase):
    def test_adjust_weights_page_exposes_pvt_and_completion_links(self):
        user = get_user_model().objects.create_user(username='tester', password='secret123')
        upload = DataUpload.objects.create(
            user=user,
            file=SimpleUploadedFile('test.csv', b'Well,Date\nA,2024-01-01\n', content_type='text/csv'),
            filename='test.csv',
            file_format='csv',
            file_size=20,
            total_rows=2,
            columns=['Well', 'Date'],
        )

        self.client.force_login(user)
        response = self.client.get(reverse('analysis:adjust_weights', kwargs={'upload_id': upload.id}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gas Constraint (MMscf/d)')
        self.assertContains(response, 'Base Choke Size')
        self.assertContains(response, 'Outlier Detection Method')
        self.assertContains(response, 'Economic Oil Limit')
        self.assertContains(response, 'Configure PVT Properties')
        self.assertContains(response, 'Upload Completion Data')
        self.assertContains(response, 'Tip: Higher weights (up to 100) give more influence')
        self.assertContains(response, 'Weight for water cut increase trends')


class ChartDataViewTests(TestCase):
    def test_get_well_data_normalizes_series_and_aligns_to_dates(self):
        user = get_user_model().objects.create_user(username='chart-tester', password='secret123')
        csv_content = (
            'Well,Date,BS&W (%),Net Oil (bopd),Form.GLR (scf/bbl),Tubing Pressure (psi)\n'
            'WELL-1,2024-01-01,5,100,800,180\n'
            'WELL-1,2024-02-01,,110,820,185\n'
            'WELL-1,2024-03-01,7,120,840,190\n'
        )
        upload = DataUpload.objects.create(
            user=user,
            file=SimpleUploadedFile('chart-data.csv', csv_content.encode('utf-8'), content_type='text/csv'),
            filename='chart-data.csv',
            file_format='csv',
            file_size=len(csv_content),
            total_rows=3,
            columns=['Well','Date','BS&W (%)','Net Oil (bopd)','Form.GLR (scf/bbl)','Tubing Pressure (psi)'],
        )
        ColumnMapping.objects.create(
            upload=upload,
            mapping={
                'Well': 'Well',
                'Date': 'Date',
                'BS&W (%)': 'BS&W (%)',
                'Net Oil (bopd)': 'Net Oil (bopd)',
                'Form.GLR (scf/bbl)': 'Form.GLR (scf/bbl)',
                'Tubing Pressure (psi)': 'Tubing Pressure (psi)',
            }
        )
        analysis = AnalysisSession.objects.create(user=user, upload=upload, status='pending')
        WellTrendAnalysis.objects.create(
            analysis=analysis,
            well_id='WELL-1',
            original_values={'bsw': [5, '', 7], 'oil_rate': [100, 110, 120]},
            corrected_values={'bsw': [1, '', 3, 4], 'oil_rate': [100, 110, 120]},
        )

        self.client.force_login(user)
        response = self.client.get(reverse('analysis:get_well_data', kwargs={'analysis_id': analysis.id, 'well_name': 'well1'}))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['dates']), len(data['bsw']))
        self.assertEqual(len(data['dates']), len(data['oil_rate']))
        self.assertGreater(len(data['dates']), 0)
        self.assertIsNone(data['bsw'][1])


class CompletionFeasibilityTests(TestCase):
    def test_json_completion_upload_updates_completion_and_trend_state(self):
        user = get_user_model().objects.create_user(username='completion-tester', password='secret123')
        upload = DataUpload.objects.create(
            user=user,
            file=SimpleUploadedFile('test.csv', b'Well,Date\nWELL-001,2024-01-01\n', content_type='text/csv'),
            filename='test.csv',
            file_format='csv',
            file_size=20,
            total_rows=2,
            columns=['Well', 'Date'],
        )
        analysis = AnalysisSession.objects.create(user=user, upload=upload, status='pending')
        WellTrendAnalysis.objects.create(analysis=analysis, well_id='WELL-001', candidate_score=10)

        self.client.force_login(user)
        response = self.client.post(
            reverse('analysis:upload_completion', kwargs={'analysis_id': analysis.id}),
            data=json.dumps([{
                'well_id': 'WELL-001',
                'mandrel_depths': [3000, 5000],
                'packer_depth': 2500,
                'tubing_id': 2.875,
                'available_compression_pressure': 2500,
            }]),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(CompletionData.objects.filter(analysis=analysis, well_id='WELL-001').exists())

        completion = CompletionData.objects.get(analysis=analysis, well_id='WELL-001')
        self.assertEqual(completion.feasibility_flag, 'feasible')

        trend = WellTrendAnalysis.objects.get(analysis=analysis, well_id='WELL-001')
        self.assertEqual(trend.completion_feasibility, 'feasible')

    def test_run_analysis_uses_completion_feasibility_for_normalized_well_ids(self):
        user = get_user_model().objects.create_user(username='completion-match-tester', password='secret123')
        csv_content = (
            'Well,Date,BS&W (%),Net Oil (bopd),Form.GLR (scf/bbl),Prod Method,Test Status,Tubing Pressure (psi),Flow Line Pressure (psi),Well Choke Size,Reservoir Pressure (psi),Flowing BHP (psi)\n'
            'WELL-001,2024-01-01,5,100,800,Gas Lift,Normal,150,100,24/64,2500,2000\n'
            'WELL-001,2024-02-01,6,105,810,Gas Lift,Normal,152,101,24/64,2490,1990\n'
            'WELL-001,2024-03-01,7,110,820,Gas Lift,Normal,154,102,24/64,2480,1980\n'
            'WELL-001,2024-04-01,8,115,830,Gas Lift,Normal,156,103,24/64,2470,1970\n'
            'WELL-001,2024-05-01,9,120,840,Gas Lift,Normal,158,104,24/64,2460,1960\n'
        )
        upload = DataUpload.objects.create(
            user=user,
            file=SimpleUploadedFile('completion-match.csv', csv_content.encode('utf-8'), content_type='text/csv'),
            filename='completion-match.csv',
            file_format='csv',
            file_size=len(csv_content),
            total_rows=5,
            columns=['Well','Date','BS&W (%)','Net Oil (bopd)','Form.GLR (scf/bbl)','Prod Method','Test Status','Tubing Pressure (psi)','Flow Line Pressure (psi)','Well Choke Size','Reservoir Pressure (psi)','Flowing BHP (psi)'],
        )
        ColumnMapping.objects.create(
            upload=upload,
            mapping={
                'Well': 'Well',
                'Date': 'Date',
                'BS&W (%)': 'BS&W (%)',
                'Net Oil (bopd)': 'Net Oil (bopd)',
                'Form.GLR (scf/bbl)': 'Form.GLR (scf/bbl)',
                'Prod Method': 'Prod Method',
                'Test Status': 'Test Status',
                'Tubing Pressure (psi)': 'Tubing Pressure (psi)',
                'Flow Line Pressure (psi)': 'Flow Line Pressure (psi)',
                'Well Choke Size': 'Well Choke Size',
                'Reservoir Pressure (psi)': 'Reservoir Pressure (psi)',
                'Flowing BHP (psi)': 'Flowing BHP (psi)',
            }
        )
        analysis = AnalysisSession.objects.create(user=user, upload=upload, status='pending')
        CompletionData.objects.create(analysis=analysis, well_id='WELL-001', feasibility_flag='feasible')

        self.client.force_login(user)
        response = self.client.post(
            reverse('analysis:run_analysis', kwargs={'analysis_id': analysis.id}),
            {'selected_wells': json.dumps(['well001'])},
        )

        self.assertEqual(response.status_code, 302)
        trend = WellTrendAnalysis.objects.get(analysis=analysis, well_id='well001')
        self.assertEqual(trend.completion_feasibility, 'feasible')

    def test_smaller_tubing_requires_higher_injection_pressure(self):
        shallow_depth = 5000
        pressure_small_tubing = CompletionFeasibilityChecker.calculate_injection_pressure_requirement(
            mandrel_depth_ft=shallow_depth,
            packer_depth_ft=3000,
            tubing_id_inch=1.5,
        )
        pressure_large_tubing = CompletionFeasibilityChecker.calculate_injection_pressure_requirement(
            mandrel_depth_ft=shallow_depth,
            packer_depth_ft=3000,
            tubing_id_inch=2.875,
        )

        self.assertGreater(pressure_small_tubing, pressure_large_tubing)


class LiquidLoadingDiagnosticsTests(SimpleTestCase):
    def test_oil_rate_is_used_to_estimate_gas_velocity(self):
        pvt = PVTProperties(api_gravity=35, gas_specific_gravity=0.65, water_salinity=20000, temperature_f=180)
        diagnostics = LiquidLoadingDiagnostics(pvt, tubing_diameter_inch=2.875)

        result = diagnostics.analyze_well(
            avg_glr_scf_bbl=1200,
            avg_tubing_pressure_psi=150,
            oil_rate_bopd=200,
        )

        self.assertIsNotNone(result['actual_velocity'])
        self.assertGreaterEqual(result['actual_velocity'], 0)
        self.assertIn(result['diagnosis'], {'LIQUID LOADED - Gas lift recommended', 'Not liquid loaded'})


class SensitivityAnalysisTests(SimpleTestCase):
    def test_run_simulation_returns_stats_for_each_well(self):
        well_data = {
            'WELL-1': [
                {'Well': 'WELL-1', 'Date': '2024-01-01', 'BS&W (%)': 5, 'Net Oil (bopd)': 100, 'Form.GLR (scf/bbl)': 800, 'Tubing Pressure (psi)': 180},
                {'Well': 'WELL-1', 'Date': '2024-02-01', 'BS&W (%)': 8, 'Net Oil (bopd)': 90, 'Form.GLR (scf/bbl)': 780, 'Tubing Pressure (psi)': 170},
                {'Well': 'WELL-1', 'Date': '2024-03-01', 'BS&W (%)': 12, 'Net Oil (bopd)': 80, 'Form.GLR (scf/bbl)': 760, 'Tubing Pressure (psi)': 160},
                {'Well': 'WELL-1', 'Date': '2024-04-01', 'BS&W (%)': 15, 'Net Oil (bopd)': 70, 'Form.GLR (scf/bbl)': 740, 'Tubing Pressure (psi)': 150},
                {'Well': 'WELL-1', 'Date': '2024-05-01', 'BS&W (%)': 18, 'Net Oil (bopd)': 60, 'Form.GLR (scf/bbl)': 720, 'Tubing Pressure (psi)': 140},
            ],
            'WELL-2': [
                {'Well': 'WELL-2', 'Date': '2024-01-01', 'BS&W (%)': 6, 'Net Oil (bopd)': 120, 'Form.GLR (scf/bbl)': 900, 'Tubing Pressure (psi)': 200},
                {'Well': 'WELL-2', 'Date': '2024-02-01', 'BS&W (%)': 7, 'Net Oil (bopd)': 118, 'Form.GLR (scf/bbl)': 900, 'Tubing Pressure (psi)': 195},
                {'Well': 'WELL-2', 'Date': '2024-03-01', 'BS&W (%)': 8, 'Net Oil (bopd)': 115, 'Form.GLR (scf/bbl)': 905, 'Tubing Pressure (psi)': 190},
                {'Well': 'WELL-2', 'Date': '2024-04-01', 'BS&W (%)': 9, 'Net Oil (bopd)': 112, 'Form.GLR (scf/bbl)': 910, 'Tubing Pressure (psi)': 185},
                {'Well': 'WELL-2', 'Date': '2024-05-01', 'BS&W (%)': 10, 'Net Oil (bopd)': 110, 'Form.GLR (scf/bbl)': 915, 'Tubing Pressure (psi)': 180},
            ],
        }
        base_weights = SimpleNamespace(
            bsw_weight=100,
            oil_rate_weight=100,
            glr_weight=100,
            tubing_pressure_weight=50,
        )

        simulator = MonteCarloSensitivity(iterations=5)
        results = simulator.run_simulation(well_data, base_weights)

        self.assertIn('WELL-1', results)
        self.assertIn('WELL-2', results)
        self.assertIn('rank_mean', results['WELL-1'])
        self.assertIn('rank_variance', results['WELL-1'])

    def test_classify_confidence_thresholds(self):
        self.assertEqual(MonteCarloSensitivity.classify_confidence(0.10), 'High')
        self.assertEqual(MonteCarloSensitivity.classify_confidence(0.20), 'Medium')
        self.assertEqual(MonteCarloSensitivity.classify_confidence(0.35), 'Low')


class RunSensitivityTests(TestCase):
    def test_run_sensitivity_honors_selected_wells(self):
        user = get_user_model().objects.create_user(username='sensitivity-tester', password='secret123')
        csv_content = (
            'Well,Date,BS&W (%),Net Oil (bopd),Form.GLR (scf/bbl),Prod Method,Test Status,Tubing Pressure (psi),Flow Line Pressure (psi),Well Choke Size\n'
            'WELL-1,2024-01-01,5,100,800,Flowing,Normal,150,100,24/64\n'
            'WELL-2,2024-01-01,6,120,900,Flowing,Normal,160,105,24/64\n'
            'WELL-3,2024-01-01,7,110,850,Flowing,Normal,155,102,24/64\n'
            'WELL-1,2024-02-01,6,105,820,Flowing,Normal,152,101,24/64\n'
            'WELL-2,2024-02-01,7,118,905,Flowing,Normal,158,104,24/64\n'
            'WELL-3,2024-02-01,8,112,860,Flowing,Normal,157,103,24/64\n'
        )
        upload = DataUpload.objects.create(
            user=user,
            file=SimpleUploadedFile('sensitivity.csv', csv_content.encode('utf-8'), content_type='text/csv'),
            filename='sensitivity.csv',
            file_format='csv',
            file_size=len(csv_content),
            total_rows=6,
            columns=['Well','Date','BS&W (%)','Net Oil (bopd)','Form.GLR (scf/bbl)','Prod Method','Test Status','Tubing Pressure (psi)','Flow Line Pressure (psi)','Well Choke Size'],
        )
        ColumnMapping.objects.create(
            upload=upload,
            mapping={
                'Well': 'Well',
                'Date': 'Date',
                'BS&W (%)': 'BS&W (%)',
                'Net Oil (bopd)': 'Net Oil (bopd)',
                'Form.GLR (scf/bbl)': 'Form.GLR (scf/bbl)',
                'Prod Method': 'Prod Method',
                'Test Status': 'Test Status',
                'Tubing Pressure (psi)': 'Tubing Pressure (psi)',
                'Flow Line Pressure (psi)': 'Flow Line Pressure (psi)',
                'Well Choke Size': 'Well Choke Size',
            }
        )
        analysis = AnalysisSession.objects.create(user=user, upload=upload, status='pending', selected_wells=['WELL-1', 'WELL-2'])

        self.client.force_login(user)
        response = self.client.get(reverse('analysis:run_sensitivity', kwargs={'analysis_id': analysis.id}))

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['status'], 'success')
        self.assertEqual(set(result['results'].keys()), {'WELL-1', 'WELL-2'})
        self.assertNotIn('WELL-3', result['results'])


class GasAllocationTests(SimpleTestCase):
    def test_gas_knapsack_ranks_by_efficiency_and_unallocated_wells(self):
        class Trend:
            def __init__(self, well_id, candidate_score, recommended_gas_mmscf):
                self.well_id = well_id
                self.candidate_score = candidate_score
                self.recommended_gas_mmscf = recommended_gas_mmscf
                self.gas_utilization_efficiency = None
                self.rank = None

        t1 = Trend('WELL-1', candidate_score=100, recommended_gas_mmscf=1.0)
        t2 = Trend('WELL-2', candidate_score=150, recommended_gas_mmscf=2.0)
        t3 = Trend('WELL-3', candidate_score=50, recommended_gas_mmscf=0.5)
        trends = [t1, t2, t3]

        _run_gas_knapsack(trends, gas_constraint_mmscf=1.5)

        ranked = sorted(trends, key=lambda t: t.rank)
        self.assertEqual([t.well_id for t in ranked], ['WELL-1', 'WELL-3', 'WELL-2'])
        self.assertEqual(ranked[0].rank, 1)
        self.assertEqual(ranked[1].rank, 2)
        self.assertEqual(ranked[2].rank, 3)
        self.assertEqual(ranked[0].gas_utilization_efficiency, 100.0)
        self.assertEqual(ranked[1].gas_utilization_efficiency, 100.0)
        self.assertEqual(ranked[2].gas_utilization_efficiency, 0.0)


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class CompareAnalysesTests(TestCase):
    def test_compare_analyses_detects_improved_deteriorated_new_and_removed_wells(self):
        user = get_user_model().objects.create_user(username='compare-tester', password='secret123')
        upload = DataUpload.objects.create(
            user=user,
            file=SimpleUploadedFile('compare.csv', b'Well,Date\n', content_type='text/csv'),
            filename='compare.csv',
            file_format='csv',
            file_size=20,
            total_rows=1,
            columns=['Well', 'Date'],
        )
        analysis_a = AnalysisSession.objects.create(user=user, upload=upload, status='completed')
        analysis_b = AnalysisSession.objects.create(user=user, upload=upload, status='completed')

        WellTrendAnalysis.objects.create(analysis=analysis_a, well_id='WELL-1', candidate_score=20, rank=2)
        WellTrendAnalysis.objects.create(analysis=analysis_b, well_id='WELL-1', candidate_score=25, rank=1)

        WellTrendAnalysis.objects.create(analysis=analysis_a, well_id='WELL-2', candidate_score=30, rank=1)
        WellTrendAnalysis.objects.create(analysis=analysis_b, well_id='WELL-2', candidate_score=18, rank=3)

        WellTrendAnalysis.objects.create(analysis=analysis_b, well_id='WELL-3', candidate_score=10, rank=4)
        WellTrendAnalysis.objects.create(analysis=analysis_a, well_id='WELL-4', candidate_score=15, rank=4)

        self.client.force_login(user)
        response = self.client.get(
            reverse('analysis:compare_analyses') + f'?analysis_a={analysis_a.id}&analysis_b={analysis_b.id}'
        )

        self.assertEqual(response.status_code, 200)
        summary = response.context['summary']
        self.assertEqual(summary['improved'], 1)
        self.assertEqual(summary['deteriorated'], 1)
        self.assertEqual(summary['unchanged'], 0)
        self.assertEqual(summary['new_wells'], 1)
        self.assertEqual(summary['removed_wells'], 1)
        self.assertContains(response, 'Improved')
        self.assertContains(response, 'Deteriorated')
        self.assertContains(response, 'New Well')
        self.assertContains(response, 'Removed')

    def test_compare_analyses_normalizes_well_ids_for_matching(self):
        user = get_user_model().objects.create_user(username='compare-tester-2', password='secret123')
        upload = DataUpload.objects.create(
            user=user,
            file=SimpleUploadedFile('compare2.csv', b'Well,Date\n', content_type='text/csv'),
            filename='compare2.csv',
            file_format='csv',
            file_size=20,
            total_rows=1,
            columns=['Well', 'Date'],
        )
        analysis_a = AnalysisSession.objects.create(user=user, upload=upload, status='completed')
        analysis_b = AnalysisSession.objects.create(user=user, upload=upload, status='completed')

        WellTrendAnalysis.objects.create(analysis=analysis_a, well_id='WELL-001 ', candidate_score=20, rank=2)
        WellTrendAnalysis.objects.create(analysis=analysis_b, well_id='well-001', candidate_score=25, rank=1)

        self.client.force_login(user)
        response = self.client.get(
            reverse('analysis:compare_analyses') + f'?analysis_a={analysis_a.id}&analysis_b={analysis_b.id}'
        )

        self.assertEqual(response.status_code, 200)
        summary = response.context['summary']
        self.assertEqual(summary['new_wells'], 0)
        self.assertEqual(summary['removed_wells'], 0)
        self.assertEqual(summary['improved'], 1)
        self.assertEqual(summary['deteriorated'], 0)
        self.assertContains(response, 'Improved')


class DataPreviewTests(SimpleTestCase):
    def test_preview_quality_report_includes_columns_detected_and_unique_wells(self):
        csv_content = """Well,Date,BS&W (%),Net Oil (bopd),Form.GLR (scf/bbl),Prod Method,Test Status,Tubing Pressure (psi),Flow Line Pressure (psi),Well Choke Size
WELL-001,2024-01-01,10,200,850,Flowing,Normal,150,100,24/64
WELL-002,2024-01-02,12,180,900,Flowing,Normal,160,105,24/64
"""
        upload = SimpleNamespace(file=io.StringIO(csv_content), file_format='csv')
        mapping = {
            'Well': 'Well',
            'Date': 'Date',
            'BS&W (%)': 'BS&W (%)',
            'Net Oil (bopd)': 'Net Oil (bopd)',
            'Form.GLR (scf/bbl)': 'Form.GLR (scf/bbl)',
            'Prod Method': 'Prod Method',
            'Test Status': 'Test Status',
            'Tubing Pressure (psi)': 'Tubing Pressure (psi)',
            'Flow Line Pressure (psi)': 'Flow Line Pressure (psi)',
            'Well Choke Size': 'Well Choke Size',
        }

        rows, quality_report, error = DataProcessor.process_data(upload, mapping)

        self.assertIsNone(error)
        self.assertEqual(len(rows), 2)
        self.assertEqual(quality_report['columns_detected'], list(mapping.values()))
        self.assertEqual(quality_report['unique_wells'], ['WELL-001', 'WELL-002'])


class DateParsingTests(SimpleTestCase):
    def test_parse_date_supports_many_common_formats(self):
        from apps.data_upload.utils import _parse_date

        self.assertEqual(_parse_date('2024-01-01').date(), datetime(2024, 1, 1).date())
        self.assertEqual(_parse_date('01/02/2024').date(), datetime(2024, 1, 2).date())
        self.assertEqual(_parse_date('02-01-2024').date(), datetime(2024, 2, 1).date())
        self.assertEqual(_parse_date('20240102').date(), datetime(2024, 1, 2).date())
        self.assertEqual(_parse_date('2024.01.02').date(), datetime(2024, 1, 2).date())
        self.assertEqual(_parse_date('2024-01-02T00:00:00Z').date(), datetime(2024, 1, 2).date())
        self.assertEqual(_parse_date('02 Jan 2024').date(), datetime(2024, 1, 2).date())
        self.assertEqual(_parse_date('02 Jan 2024 12:00 PM').date(), datetime(2024, 1, 2).date())
        self.assertEqual(_parse_date('1st Feb 2024').date(), datetime(2024, 2, 1).date())
        self.assertEqual(_parse_date('2nd Mar 2024').date(), datetime(2024, 3, 2).date())
        self.assertEqual(_parse_date('3rd Apr 2024').date(), datetime(2024, 4, 3).date())
        self.assertEqual(_parse_date('4th May 2024').date(), datetime(2024, 5, 4).date())

    def test_trend_analysis_falls_back_when_dates_are_invalid(self):
        from apps.analysis.utils import TrendAnalyzer

        data_series = [100, 90, 80, 70, 60]
        time_series = ['invalid', 'invalid', 'invalid', 'invalid', 'invalid']

        trend, tau, p_value = TrendAnalyzer.mann_kendall_test(data_series, time_series=time_series)
        self.assertIn(trend, {'decreasing', 'no_trend'})
        self.assertLessEqual(abs(tau), 1)
        self.assertIsInstance(p_value, float)

        slope = TrendAnalyzer.sen_slope(data_series, time_series=time_series)
        self.assertLess(slope, 0)

    def test_analyze_well_scores_with_weak_but_directional_trends(self):
        from apps.analysis.utils import TrendAnalyzer
        from apps.analysis.models import AnalysisWeights

        weights = AnalysisWeights(
            bsw_weight=100,
            oil_rate_weight=100,
            glr_weight=100,
            tubing_pressure_weight=50,
        )

        well_data = [
            {'Date': '01/01/2024', 'BS&W (%)': 10, 'Net Oil (bopd)': 200, 'Form.GLR (scf/bbl)': 900, 'Tubing Pressure (psi)': 180, 'Well Choke Size': '24/64'},
            {'Date': '02/01/2024', 'BS&W (%)': 11, 'Net Oil (bopd)': 198, 'Form.GLR (scf/bbl)': 895, 'Tubing Pressure (psi)': 179, 'Well Choke Size': '24/64'},
            {'Date': '03/01/2024', 'BS&W (%)': 12, 'Net Oil (bopd)': 196, 'Form.GLR (scf/bbl)': 890, 'Tubing Pressure (psi)': 178, 'Well Choke Size': '24/64'},
            {'Date': '04/01/2024', 'BS&W (%)': 13, 'Net Oil (bopd)': 194, 'Form.GLR (scf/bbl)': 885, 'Tubing Pressure (psi)': 177, 'Well Choke Size': '24/64'},
            {'Date': '05/01/2024', 'BS&W (%)': 14, 'Net Oil (bopd)': 192, 'Form.GLR (scf/bbl)': 880, 'Tubing Pressure (psi)': 176, 'Well Choke Size': '24/64'},
        ]

        result = TrendAnalyzer.analyze_well(well_data, weights)

        self.assertGreater(result['candidate_score'], 0)
        self.assertEqual(result['bsw_trend'], 'increasing')
        self.assertEqual(result['oil_rate_trend'], 'decreasing')
        self.assertEqual(result['glr_trend'], 'decreasing')
        self.assertEqual(result['tubing_pressure_trend'], 'decreasing')

    def test_analyze_well_scores_decline_trends(self):
        from apps.analysis.utils import TrendAnalyzer
        from apps.analysis.models import AnalysisWeights

        weights = AnalysisWeights(
            bsw_weight=100,
            oil_rate_weight=100,
            glr_weight=100,
            tubing_pressure_weight=50,
        )

        # Synthetic declining oil and GLR, increasing BSW
        well_data = [
            {'Date': '2024-01-01', 'BS&W (%)': 10, 'Net Oil (bopd)': 200, 'Form.GLR (scf/bbl)': 900, 'Tubing Pressure (psi)': 180, 'Well Choke Size': '24/64'},
            {'Date': '2024-02-01', 'BS&W (%)': 12, 'Net Oil (bopd)': 190, 'Form.GLR (scf/bbl)': 880, 'Tubing Pressure (psi)': 178, 'Well Choke Size': '24/64'},
            {'Date': '2024-03-01', 'BS&W (%)': 14, 'Net Oil (bopd)': 180, 'Form.GLR (scf/bbl)': 860, 'Tubing Pressure (psi)': 176, 'Well Choke Size': '24/64'},
            {'Date': '2024-04-01', 'BS&W (%)': 15, 'Net Oil (bopd)': 170, 'Form.GLR (scf/bbl)': 840, 'Tubing Pressure (psi)': 175, 'Well Choke Size': '24/64'},
            {'Date': '2024-05-01', 'BS&W (%)': 16, 'Net Oil (bopd)': 160, 'Form.GLR (scf/bbl)': 820, 'Tubing Pressure (psi)': 174, 'Well Choke Size': '24/64'},
        ]

        result = TrendAnalyzer.analyze_well(well_data, weights)

        self.assertGreater(result['candidate_score'], 0)
        self.assertEqual(result['oil_rate_trend'], 'decreasing')
        self.assertEqual(result['glr_trend'], 'decreasing')
        self.assertEqual(result['bsw_trend'], 'increasing')


class ReportingTests(SimpleTestCase):
    def test_executive_report_mentions_selected_well_scope(self):
        analysis = SimpleNamespace(
            upload=SimpleNamespace(filename='sample.csv'),
            selected_wells=['WELL-001', 'WELL-002'],
            status='completed',
            completed_at=datetime(2026, 1, 1, 12, 0),
            get_status_display=lambda: 'Completed',
        )

        class StubQuerySet(list):
            def count(self):
                return len(self)

            def filter(self, **kwargs):
                return StubQuerySet([item for item in self if all(getattr(item, key, None) == value for key, value in kwargs.items())])

            def exclude(self, **kwargs):
                return StubQuerySet([item for item in self if not all(getattr(item, key, None) == value for key, value in kwargs.items())])

            def aggregate(self, *args, **kwargs):
                if args:
                    aggregate = args[0]
                    field_name = aggregate.get_source_expressions()[0].name if aggregate.get_source_expressions() else None
                    if field_name is None:
                        return {}
                    if aggregate.__class__.__name__ == 'Avg':
                        return {f'{field_name}__avg': sum(getattr(item, field_name, 0) for item in self) / len(self) if self else 0}
                    if aggregate.__class__.__name__ == 'Max':
                        return {f'{field_name}__max': max(getattr(item, field_name, 0) for item in self) if self else 0}
                    if aggregate.__class__.__name__ == 'Min':
                        return {f'{field_name}__min': min(getattr(item, field_name, 0) for item in self) if self else 0}
                    if aggregate.__class__.__name__ == 'Sum':
                        return {f'{field_name}__sum': sum(getattr(item, field_name, 0) for item in self) if self else 0}
                    if aggregate.__class__.__name__ == 'Count':
                        return {f'{field_name}__count': len(self)}
                    return {}
                return {key: sum(getattr(item, key, 0) for item in self) for key in kwargs}

            def values(self, *args, **kwargs):
                return StubQuerySet([SimpleNamespace(completion_feasibility=getattr(item, 'completion_feasibility', 'unknown')) for item in self])

            def annotate(self, *args, **kwargs):
                return [
                    {**item.__dict__, 'count': 1}
                    for item in self
                ]

        well_trends = StubQuerySet([
            SimpleNamespace(
                well_id='WELL-001',
                rank=1,
                candidate_score=30,
                bsw_flag=False,
                oil_rate_flag=True,
                glr_flag=False,
                liquid_loading_flag=False,
                completion_feasibility='feasible',
                bsw_trend='increasing',
                oil_rate_trend='decreasing',
                glr_trend='stable',
                tubing_pressure_trend='stable',
                pi_trend='stable',
                bsw_slope=0.1,
                bsw_magnitude=1.0,
                oil_rate_slope=-0.5,
                oil_rate_magnitude=2.0,
                glr_slope=0.0,
                glr_magnitude=0.0,
                tubing_pressure_slope=0.0,
                tubing_pressure_magnitude=0.0,
                summary_comment='Test summary',
                prod_method='Flowing',
                data_quality_score=95.0,
                outlier_count=1,
                critical_velocity=2.5,
                actual_velocity=3.0,
                critical_glr=1000,
                actual_glr=900,
                productivity_index=1.2,
                days_to_economic_limit=60,
                projected_oil_rate_6mo=150,
                recommended_gas_mmscf=0.5,
                gas_utilization_efficiency=80,
            )
        ])

        html = ReportGenerator.generate_executive_html(analysis, well_trends)

        self.assertIn('Selected well scope', html)
        self.assertIn('2 selected well(s)', html)
        self.assertIn('Analysis status: Completed', html)
        self.assertIn('Analysis was completed successfully and results were processed.', html)
