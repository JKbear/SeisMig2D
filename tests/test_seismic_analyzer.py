"""Tests for seismic_analyzer module"""
import sys
import os
import pytest
import numpy as np

project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

from src.seismic_analyzer import BearingAnalyzer, MigrationAnalyzer, BearingAnalysisResult

class TestBearingAnalyzer:
    """Test BearingAnalyzer class"""

    def test_calculate_event_pairs(self, sample_events):
        analyzer = BearingAnalyzer()
        bearings, distances, weights = analyzer.calculate_event_pairs(
            sample_events, min_distance_km=1.0, max_distance_km=500.0
        )
        assert len(bearings) == len(distances) == len(weights)
        assert np.all(bearings >= 0)
        assert np.all(bearings < 360)
        assert np.all(distances >= 1.0)
        assert np.all(weights > 0)

    def test_calculate_event_pairs_empty(self):
        analyzer = BearingAnalyzer()
        bearings, distances, weights = analyzer.calculate_event_pairs([])
        assert len(bearings) == 0

    def test_create_histogram(self, sample_events):
        analyzer = BearingAnalyzer()
        bearings, _, _ = analyzer.calculate_event_pairs(sample_events)
        if len(bearings) > 0:
            histogram, bin_edges, bin_centers = analyzer.create_histogram(bearings)
            assert len(histogram) == analyzer.bins
            assert len(bin_centers) == analyzer.bins
            assert np.all(histogram >= 0)

    def test_detect_peaks(self, sample_events):
        analyzer = BearingAnalyzer()
        bearings, _, _ = analyzer.calculate_event_pairs(sample_events)
        if len(bearings) > 0:
            histogram, _, bin_centers = analyzer.create_histogram(bearings)
            peaks, peak_properties = analyzer.detect_peaks(histogram, bin_centers)
            assert 'peak_heights' in peak_properties
            assert 'peak_positions' in peak_properties

    def test_fit_gaussians(self, sample_events):
        analyzer = BearingAnalyzer()
        bearings, _, _ = analyzer.calculate_event_pairs(sample_events)
        if len(bearings) > 0:
            histogram, _, bin_centers = analyzer.create_histogram(bearings)
            peaks, _ = analyzer.detect_peaks(histogram, bin_centers)
            if len(peaks) > 0:
                fits = analyzer.fit_gaussians(histogram, bin_centers, peaks)
                # Gaussian fitting may fail for small datasets - just verify it runs
                assert isinstance(fits, list)

    def test_analyze_bearings(self, sample_events):
        analyzer = BearingAnalyzer()
        result = analyzer.analyze_bearings(sample_events)
        assert isinstance(result, BearingAnalysisResult)
        assert len(result.bearings) > 0
        assert 'total_pairs' in result.statistics

    def test_analyze_bearings_insufficient_events(self):
        analyzer = BearingAnalyzer()
        with pytest.raises(ValueError):
            analyzer.analyze_bearings([])

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
