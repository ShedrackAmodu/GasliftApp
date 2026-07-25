import io
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.analysis.completion import CompletionFeasibilityChecker
from apps.analysis.reporting import ReportGenerator
from apps.data_upload.utils import DataProcessor
from apps.analysis.ipr_calculator import LiquidLoadingDiagnostics
from apps.analysis.pvt import PVTProperties
from apps.analysis.sensitivity import MonteCarloSensitivity
from apps.data_upload.models import DataUpload


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


class CompletionFeasibilityTests(SimpleTestCase):
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
                {'Well': 'WELL-2', 'Date': '2024-03-01', 'BS&W (%)': 8, 'Net Oil (bopd)': 115, 'Net Oil (bopd)': 115, 'Form.GLR (scf/bbl)': 905, 'Tubing Pressure (psi)': 190},
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


class ReportingTests(SimpleTestCase):
    def test_executive_report_mentions_selected_well_scope(self):
        analysis = SimpleNamespace(
            upload=SimpleNamespace(filename='sample.csv'),
            selected_wells=['WELL-001', 'WELL-002'],
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
