"""Tests for catalog_reader module"""
import sys
import os
import pytest
from datetime import datetime

project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

from src.catalog_reader import CSVCatalogReader, TextCatalogReader, CatalogReaderFactory, EarthquakeEvent

class TestEarthquakeEvent:
    """Test EarthquakeEvent dataclass"""

    def test_event_creation(self):
        event = EarthquakeEvent(
            time=datetime(2023, 1, 1),
            latitude=35.0,
            longitude=-118.0,
            depth=10.0,
            magnitude=3.5
        )
        assert event.latitude == 35.0
        assert event.longitude == -118.0
        assert event.depth == 10.0
        assert event.magnitude == 3.5
        assert event.time == datetime(2023, 1, 1)

    def test_event_optional_time(self):
        event = EarthquakeEvent(
            latitude=35.0,
            longitude=-118.0,
            depth=10.0,
            magnitude=3.5
        )
        assert event.time is None

class TestCSVCatalogReader:
    """Test CSV catalog reader"""

    def test_read_csv_with_header(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "latitude,longitude,magnitude,depth,time\n"
            "35.0,-118.0,3.5,10.0,2023-01-01 00:00:00\n"
            "35.1,-118.1,3.6,11.0,2023-01-02 00:00:00\n"
        )
        reader = CSVCatalogReader()
        events = reader.read_file(str(csv_file))
        assert len(events) == 2
        assert events[0].latitude == 35.0
        assert events[1].magnitude == 3.6

    def test_read_csv_fallback_columns(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "lat,lon,mag,depth,time\n"
            "35.0,-118.0,3.5,10.0,2023-01-01 00:00:00\n"
        )
        reader = CSVCatalogReader()
        events = reader.read_file(str(csv_file))
        assert len(events) == 1

class TestTextCatalogReader:
    """Test fixed-format text catalog reader"""

    def test_read_text_catalog(self, tmp_path):
        text_file = tmp_path / "test.txt"
        text_file.write_text(
            "2023  1  1  0  0  0 -118.0  35.0  3.5  10.0\n"
            "2023  1  2  0  0  0 -118.1  35.1  3.6  11.0\n"
        )
        reader = TextCatalogReader()
        events = reader.read_file(str(text_file))
        assert len(events) == 2
        assert events[0].latitude == 35.0
        assert events[0].magnitude == 3.5

class TestCatalogReaderFactory:
    """Test catalog reader factory"""

    def test_factory_csv(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("latitude,longitude,magnitude,depth,time\n35.0,-118.0,3.5,10.0,2023-01-01 00:00:00")
        events = CatalogReaderFactory.read_catalog(str(csv_file))
        assert isinstance(events, list)
        assert len(events) == 1
        assert events[0].latitude == 35.0

    def test_factory_text(self, tmp_path):
        text_file = tmp_path / "test.txt"
        text_file.write_text("2023  1  1  0  0  0 -118.0  35.0  3.5  10.0")
        events = CatalogReaderFactory.read_catalog(str(text_file))
        assert isinstance(events, list)
        assert len(events) == 1

    def test_factory_file_not_found(self):
        with pytest.raises(ValueError):
            CatalogReaderFactory.read_catalog("/nonexistent/file.csv")
