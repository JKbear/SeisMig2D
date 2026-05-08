"""Tests for seismic_analyzer module"""
import sys
import os
import pytest
import numpy as np

project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

from src.seismic_analyzer import DirectivityAnalyzer, MigrationAnalyzer, DirectivityAnalysisResult, TemporalDirectivityResult

class TestDirectivityAnalyzer:
    """Test DirectivityAnalyzer class"""

    def test_calculate_event_pairs(self, sample_events):
        analyzer = DirectivityAnalyzer()
        directivities, distances, weights, _, _, _ = analyzer.calculate_event_pairs(
            sample_events, min_distance_km=1.0, max_distance_km=500.0
        )
        assert len(directivities) == len(distances) == len(weights)
        assert np.all(directivities >= 0)
        assert np.all(directivities < 360)
        assert np.all(distances >= 1.0)
        assert np.all(weights > 0)

    def test_calculate_event_pairs_empty(self):
        analyzer = DirectivityAnalyzer()
        directivities, distances, weights, _, _, _ = analyzer.calculate_event_pairs([])
        assert len(directivities) == 0

    def test_create_histogram(self, sample_events):
        analyzer = DirectivityAnalyzer()
        directivities, _, _, _, _, _ = analyzer.calculate_event_pairs(sample_events)
        if len(directivities) > 0:
            histogram, bin_edges, bin_centers = analyzer.create_histogram(directivities)
            assert len(histogram) == analyzer.bins
            assert len(bin_centers) == analyzer.bins
            assert np.all(histogram >= 0)

    def test_detect_peaks(self, sample_events):
        analyzer = DirectivityAnalyzer()
        directivities, _, _, _, _, _ = analyzer.calculate_event_pairs(sample_events)
        if len(directivities) > 0:
            histogram, _, bin_centers = analyzer.create_histogram(directivities)
            peaks, peak_properties = analyzer.detect_peaks(histogram, bin_centers)
            assert 'peak_heights' in peak_properties
            assert 'peak_positions' in peak_properties

    def test_fit_gaussians(self, sample_events):
        analyzer = DirectivityAnalyzer()
        directivities, _, _, _, _, _ = analyzer.calculate_event_pairs(sample_events)
        if len(directivities) > 0:
            histogram, _, bin_centers = analyzer.create_histogram(directivities)
            peaks, _ = analyzer.detect_peaks(histogram, bin_centers)
            if len(peaks) > 0:
                fits = analyzer.fit_gaussians(histogram, bin_centers, peaks)
                # Gaussian fitting may fail for small datasets - just verify it runs
                assert isinstance(fits, list)

    def test_analyze_directivities(self, sample_events):
        analyzer = DirectivityAnalyzer()
        result = analyzer.analyze_directivities(sample_events)
        assert isinstance(result, DirectivityAnalysisResult)
        assert len(result.directivities) > 0
        assert 'total_pairs' in result.statistics

    def test_analyze_directivities_insufficient_events(self):
        analyzer = DirectivityAnalyzer()
        with pytest.raises(ValueError):
            analyzer.analyze_directivities([])

    def test_count_samples_in_peak_region(self):
        """Test counting samples within a peak region"""
        directivities = np.array([45.0, 90.0, 225.0, 270.0])
        count = DirectivityAnalyzer.count_samples_in_peak_region(
            directivities, peak_center=90.0, half_width=30.0
        )
        assert count == 1

        # Test boundary crossing (350°, 10° -> should be within 30° of 0°)
        directivities2 = np.array([350.0, 5.0, 10.0, 100.0])
        count2 = DirectivityAnalyzer.count_samples_in_peak_region(
            directivities2, peak_center=0.0, half_width=20.0
        )
        assert count2 == 3

    def test_calculate_confidence_intervals(self):
        """Test 95% CI narrows as N increases"""
        N = np.array([100, 400, 900])
        lower, upper = DirectivityAnalyzer.calculate_confidence_intervals(N)
        assert len(lower) == 3
        assert len(upper) == 3
        # Larger N should give narrower intervals
        assert (upper[2] - lower[2]) < (upper[0] - lower[0])

class TestMigrationAnalyzer:
    """Test MigrationAnalyzer class"""

    def test_spatial_analysis(self, sample_events):
        analyzer = MigrationAnalyzer()
        result = analyzer.spatial_analysis(sample_events)
        assert 'latitude_stats' in result
        assert 'spatial_density' in result
        assert result['spatial_density'] > 0

    def test_magnitude_analysis(self, sample_events):
        analyzer = MigrationAnalyzer()
        result = analyzer.magnitude_analysis(sample_events)
        assert 'magnitude_stats' in result
        assert 'b_value_estimate' in result

    def test_temporal_analysis(self, sample_events):
        analyzer = MigrationAnalyzer()
        result = analyzer.temporal_analysis(sample_events, time_window_days=5)
        assert 'time_series_stats' in result or 'window_analysis' in result

    def test_comprehensive_analysis(self, synthetic_north_south_migration):
        analyzer = MigrationAnalyzer()
        result = analyzer.comprehensive_analysis(
            synthetic_north_south_migration,
            min_distance_km=1.0,
            max_distance_km=50.0,
            time_window_days=10
        )
        assert result.temporal_analysis is not None
        assert result.spatial_analysis is not None
        assert result.directional_analysis is not None
        assert result.magnitude_analysis is not None

    def test_comprehensive_analysis_insufficient_events(self):
        analyzer = MigrationAnalyzer()
        with pytest.raises(ValueError):
            analyzer.comprehensive_analysis([])

    def test_temporal_directivity_ratio_analysis(self, synthetic_north_south_migration):
        analyzer = MigrationAnalyzer()
        result = analyzer.temporal_directivity_ratio_analysis(
            synthetic_north_south_migration,
            window_sizes=[1.0, 2.0],
            time_step=0.5,
            peak_half_width=30,
            min_events=2,
        )
        assert isinstance(result, TemporalDirectivityResult)
        assert len(result.window_sizes) == 2
        assert len(result.times_by_window) == 2
        assert len(result.ratios_by_window) == 2
        assert 'total_windows_computed' in result.statistics
