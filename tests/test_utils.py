"""Tests for utils module"""
import sys
import os
import pytest
import numpy as np

project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

from src.utils import (
    GeometryCalculator, CoordinateConverter, DataValidator,
    StatisticsCalculator, convert_numpy_types
)

class TestGeometryCalculator:
    """Test GeometryCalculator class"""

    def test_calculate_distance(self):
        # Known distance: ~111km per degree at equator
        dist = GeometryCalculator.calculate_distance(0, 0, 0, 1)
        assert 108 <= dist <= 112  # roughly 111km

    def test_calculate_distance_same_point(self):
        dist = GeometryCalculator.calculate_distance(35, -118, 35, -118)
        assert dist == 0

    def test_calculate_bearing_north(self):
        bearing = GeometryCalculator.calculate_bearing(0, 0, 1, 0)
        # Moving north should be around 0 degrees (or 360)
        assert (bearing < 10) or (bearing > 350)

    def test_calculate_bearing_east(self):
        bearing = GeometryCalculator.calculate_bearing(0, 0, 0, 1)
        assert 85 <= bearing <= 95  # roughly east

    def test_calculate_bearing_range(self, synthetic_random):
        # Test that bearing is always in [0, 360)
        for _ in range(10):
            lat1 = np.random.uniform(-90, 90)
            lon1 = np.random.uniform(-180, 180)
            lat2 = np.random.uniform(-90, 90)
            lon2 = np.random.uniform(-180, 180)
            bearing = GeometryCalculator.calculate_bearing(lat1, lon1, lat2, lon2)
            assert 0 <= bearing < 360

    def test_calculate_distance_and_bearing(self):
        dist, bearing = GeometryCalculator.calculate_distance_and_bearing(0, 0, 1, 1)
        assert 0 <= bearing < 360
        assert dist > 0

class TestCoordinateConverter:
    """Test CoordinateConverter class"""

    def test_initialization(self):
        converter = CoordinateConverter()
        assert converter.transformer is not None

    def test_wgs84_to_web_mercator(self):
        converter = CoordinateConverter()
        x, y = converter.wgs84_to_web_mercator(-118.0, 35.0)
        assert isinstance(x, float)
        assert isinstance(y, float)

    def test_batch_convert(self):
        converter = CoordinateConverter()
        lons = np.array([-118.0, -119.0])
        lats = np.array([35.0, 36.0])
        xs, ys = converter.batch_convert(lons, lats)
        assert len(xs) == 2
        assert len(ys) == 2

class TestDataValidator:
    """Test DataValidator class"""

    def test_validate_coordinates_valid(self):
        assert DataValidator.validate_coordinates(35.0, -118.0)
        assert DataValidator.validate_coordinates(0, 0)
        assert DataValidator.validate_coordinates(-90, 180)

    def test_validate_coordinates_invalid(self):
        assert not DataValidator.validate_coordinates(91, 0)
        assert not DataValidator.validate_coordinates(0, 181)
        assert not DataValidator.validate_coordinates(-91, 0)

    def test_validate_magnitude_valid(self):
        assert DataValidator.validate_magnitude(3.5)
        assert DataValidator.validate_magnitude(0)
        assert DataValidator.validate_magnitude(-5)

    def test_validate_magnitude_invalid(self):
        assert not DataValidator.validate_magnitude(11)
        assert not DataValidator.validate_magnitude(-11)

    def test_validate_depth_valid(self):
        assert DataValidator.validate_depth(10)
        assert DataValidator.validate_depth(0)
        assert DataValidator.validate_depth(-50)

    def test_validate_depth_invalid(self):
        assert not DataValidator.validate_depth(-101)
        assert not DataValidator.validate_depth(1001)

    def test_validate_time_string(self):
        assert DataValidator.validate_time_string("2023-01-01 00:00:00")
        assert DataValidator.validate_time_string("2023/01/01 00:00:00")

class TestStatisticsCalculator:
    """Test StatisticsCalculator class"""

    def test_calculate_statistics(self):
        data = np.array([1, 2, 3, 4, 5])
        stats = StatisticsCalculator.calculate_statistics(data)
        assert stats['mean'] == 3.0
        assert stats['min'] == 1
        assert stats['max'] == 5
        assert stats['median'] == 3.0

    def test_calculate_statistics_empty(self):
        stats = StatisticsCalculator.calculate_statistics(np.array([]))
        assert stats['count'] == 0

    def test_calculate_circular_statistics(self):
        angles = np.array([0, 90, 180, 270])
        stats = StatisticsCalculator.calculate_circular_statistics(angles)
        assert 'circular_mean' in stats
        assert 'circular_std' in stats
        assert 'resultant_length' in stats

    def test_calculate_circular_statistics_empty(self):
        stats = StatisticsCalculator.calculate_circular_statistics(np.array([]))
        assert stats['circular_mean'] == 0.0

class TestConvertNumpyTypes:
    """Test numpy type conversion utility"""

    def test_convert_integer(self):
        result = convert_numpy_types(np.int64(42))
        assert isinstance(result, int)

    def test_convert_float(self):
        result = convert_numpy_types(np.float64(3.14))
        assert isinstance(result, float)

    def test_convert_array(self):
        result = convert_numpy_types(np.array([1, 2, 3]))
        assert isinstance(result, list)

    def test_convert_dict(self):
        result = convert_numpy_types({'a': np.int64(1), 'b': np.float64(2.0)})
        assert isinstance(result, dict)
        assert isinstance(result['a'], int)
        assert isinstance(result['b'], float)
