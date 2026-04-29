"""Pytest fixtures for SeisMig2D tests"""
import sys
import os
import pytest
import numpy as np
from datetime import datetime, timedelta

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

from src.catalog_reader import EarthquakeEvent

@pytest.fixture
def sample_events():
    """Create sample earthquake events for testing"""
    events = []
    base_time = datetime(2023, 1, 1)
    for i in range(20):
        event = EarthquakeEvent(
            time=base_time + timedelta(days=i),
            latitude=35.0 + i * 0.05,
            longitude=-118.0 + i * 0.03,
            depth=10.0 + i * 0.5,
            magnitude=2.0 + i * 0.1
        )
        events.append(event)
    return events

@pytest.fixture
def synthetic_north_south_migration():
    """Create synthetic north-south migration pattern"""
    events = []
    base_time = datetime(2023, 1, 1)
    for i in range(30):
        event = EarthquakeEvent(
            time=base_time + timedelta(days=i * 0.5),
            latitude=35.0 + i * 0.08,
            longitude=-118.0 + np.random.uniform(-0.05, 0.05),
            depth=10.0 + np.random.uniform(-3, 3),
            magnitude=2.5 + np.random.uniform(0, 1)
        )
        events.append(event)
    return events

@pytest.fixture
def synthetic_random():
    """Create random scattered events"""
    np.random.seed(42)
    events = []
    base_time = datetime(2023, 1, 1)
    for i in range(50):
        event = EarthquakeEvent(
            time=base_time + timedelta(days=np.random.uniform(0, 100)),
            latitude=35.0 + np.random.uniform(-1, 1),
            longitude=-118.0 + np.random.uniform(-1, 1),
            depth=np.random.uniform(5, 20),
            magnitude=np.random.uniform(1.5, 4.5)
        )
        events.append(event)
    return events
