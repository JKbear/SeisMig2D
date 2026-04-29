#!/usr/bin/env python3
"""
Regional Seismic Migration Study Example

Demonstrates multi-scale analysis with different distance ranges and time windows,
suitable for regional-scale seismic migration studies.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.catalog_reader import CatalogReaderFactory, EarthquakeEvent, filter_events_by_magnitude
from src.seismic_analyzer import MigrationAnalyzer, calculate_bearings
import numpy as np
from datetime import datetime, timedelta


def main():
    print("Regional Seismic Migration Study")
    print("=" * 50)

    # Load or create data
    catalog_file = "../data/ding-zhou_eqs-2023_tk-palm_v4_v2.ctlg"
    if os.path.exists(catalog_file):
        print(f"Loading regional catalog: {catalog_file}")
        events = CatalogReaderFactory.read_catalog(catalog_file)
    else:
        print("Creating synthetic regional data...")
        events = create_regional_synthetic_data()

    print(f"Total events: {len(events)}")

    # Filter by magnitude for regional study
    events = filter_events_by_magnitude(events, min_mag=2.0)
    print(f"After M >= 2.0 filter: {len(events)} events")

    analyzer = MigrationAnalyzer()

    # Study 1: Distance-dependent analysis
    print("\n--- Distance-Dependent Analysis ---")
    distance_ranges = [(0.1, 10.0), (10.0, 50.0), (50.0, 500.0)]
    for min_d, max_d in distance_ranges:
        result = calculate_bearings(events, min_distance_km=min_d, max_distance_km=max_d)
        stats = result.statistics
        dom = result.gaussian_fits[0]['mean'] if result.gaussian_fits else None
        print(f"  {min_d:5.1f}–{max_d:5.1f} km: {stats['total_pairs']:5d} pairs, "
              f"mean bearing: {stats['mean_bearing']:6.1f}°, "
              f"dominant: {dom if dom else 'N/A'}")

    # Study 2: Multi-window temporal analysis
    print("\n--- Multi-Window Temporal Analysis ---")
    time_windows = [7, 30, 90]
    for tw in time_windows:
        temporal = analyzer.temporal_analysis(events, time_window_days=tw)
        windows = temporal.get('window_analysis', [])
        directions = [w['dominant_direction'] for w in windows if w['dominant_direction'] is not None]
        if directions:
            print(f"  {tw:2d}-day window: {len(windows)} windows, "
                  f"mean dominant direction: {np.mean(directions):.1f}°, "
                  f"std: {np.std(directions):.1f}°")
        else:
            print(f"  {tw:2d}-day window: {len(windows)} windows, no clear directions")

    # Study 3: Spatial statistics
    print("\n--- Spatial Statistics ---")
    spatial = analyzer.spatial_analysis(events)
    sr = spatial.get('spatial_range', {})
    print(f"  Latitude range:  {sr.get('latitude_range', 0):.3f}°")
    print(f"  Longitude range: {sr.get('longitude_range', 0):.3f}°")
    print(f"  Spatial density: {spatial.get('spatial_density', 0):.3f} events/km^2")

    # Study 4: Magnitude analysis
    print("\n--- Magnitude Analysis ---")
    mag = analyzer.magnitude_analysis(events)
    ms = mag.get('magnitude_stats', {})
    print(f"  Magnitude range: {ms.get('min', 0):.1f} – {ms.get('max', 0):.1f}")
    print(f"  Mean magnitude: {ms.get('mean', 0):.2f}")
    print(f"  b-value estimate: {mag.get('b_value_estimate', 0):.3f}")

    # Visualization
    try:
        from src.visualizer import create_analysis_dashboard
        result = analyzer.comprehensive_analysis(events, time_window_days=30)
        create_analysis_dashboard(
            events, result,
            title="Regional Migration Analysis Dashboard",
            save_filename="regional_study_dashboard.png"
        )
        print("\n  Dashboard saved to figures/regional_study_dashboard.png")
    except Exception as e:
        print(f"\n  Dashboard error: {e}")

    print("\nRegional study complete!")


def create_regional_synthetic_data():
    """Create synthetic regional data with multiple spatial clusters."""
    np.random.seed(42)
    events = []
    base_time = datetime(2020, 1, 1)

    # Cluster 1: SW region
    for i in range(80):
        events.append(EarthquakeEvent(
            time=base_time + timedelta(days=i * 2),
            latitude=35.0 + np.random.uniform(-0.3, 0.3),
            longitude=-118.5 + np.random.uniform(-0.3, 0.3),
            depth=np.random.uniform(5, 15),
            magnitude=1.5 + np.random.exponential(0.8)
        ))

    # Cluster 2: NE region (later in time)
    for i in range(60):
        events.append(EarthquakeEvent(
            time=base_time + timedelta(days=100 + i * 2),
            latitude=36.0 + np.random.uniform(-0.2, 0.2),
            longitude=-117.5 + np.random.uniform(-0.2, 0.2),
            depth=np.random.uniform(3, 12),
            magnitude=1.5 + np.random.exponential(0.6)
        ))

    return events


if __name__ == "__main__":
    main()
