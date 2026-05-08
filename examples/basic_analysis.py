#!/usr/bin/env python3
"""
Basic Seismic Migration Analysis Example

This script demonstrates the basic usage of the SeisMig2D analysis tool.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.catalog_reader import CatalogReaderFactory, EarthquakeEvent
from src.seismic_analyzer import analyze_seismicity_migration, calculate_directivities
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta


def main():
    print("SeisMig2D — Basic Analysis Example")
    print("=" * 50)

    # Step 1: Load or create data
    sample_file = "../data/Case1_random_2faults.csv"
    if os.path.exists(sample_file):
        print(f"Loading earthquake catalog from {sample_file}...")
        events = CatalogReaderFactory.read_catalog(sample_file)
        print(f"Loaded {len(events)} earthquake events")
    else:
        print("Sample file not found, creating synthetic data...")
        events = create_synthetic_data()

    # Step 2: Directivity-only analysis (fast)
    print("\nRunning directivity analysis...")
    directivity_results = calculate_directivities(
        events=events,
        min_distance_km=0.1,
        max_distance_km=100.0
    )
    print_directivity_summary(directivity_results)

    # Step 3: Comprehensive migration analysis (slower, use --full-analysis equivalent)
    print("\nRunning comprehensive migration analysis...")
    results = analyze_seismicity_migration(
        events=events,
        min_distance_km=0.1,
        max_distance_km=100.0,
        time_window_days=30
    )
    print_analysis_summary(results)

    # Step 4: Create visualization
    print("\nCreating visualizations...")
    create_visualizations(events, directivity_results, results)

    print("\nAnalysis complete!")


def create_synthetic_data():
    """Create synthetic earthquake data with a clear migration pattern."""
    events = []
    base_time = datetime(2023, 1, 1)
    for i in range(50):
        event = EarthquakeEvent(
            time=base_time + timedelta(days=i * 0.5),
            latitude=35.0 + i * 0.02,
            longitude=-118.0 + i * 0.03,
            depth=10.0 + np.random.uniform(-5, 5),
            magnitude=2.0 + np.random.uniform(0, 3)
        )
        events.append(event)
    return events


def print_analysis_summary(results):
    """Print comprehensive analysis summary using v4 API."""
    print("\n" + "=" * 50)
    print("COMPREHENSIVE ANALYSIS RESULTS")
    print("=" * 50)

    summary = results.summary_statistics
    print(f"Total events analyzed: {summary.get('total_events', 'N/A')}")

    # Temporal analysis
    temporal = results.temporal_analysis
    if temporal:
        ts_stats = temporal.get('time_series_stats', {})
        print(f"\nTemporal Analysis:")
        print(f"  Total duration: {ts_stats.get('total_duration_days', 'N/A'):.1f} days")
        print(f"  Mean inter-event time: {ts_stats.get('mean', 'N/A'):.1f} hours")

    # Spatial analysis
    spatial = results.spatial_analysis
    if spatial:
        print(f"\nSpatial Analysis:")
        sr = spatial.get('spatial_range', {})
        print(f"  Latitude range: {sr.get('latitude_range', 'N/A'):.3f}°")
        print(f"  Longitude range: {sr.get('longitude_range', 'N/A'):.3f}°")
        print(f"  Spatial density: {spatial.get('spatial_density', 'N/A'):.3f} events/km^2")

    # Magnitude analysis
    mag = results.magnitude_analysis
    if mag:
        print(f"\nMagnitude Analysis:")
        ms = mag.get('magnitude_stats', {})
        print(f"  Magnitude range: {ms.get('min', 0):.1f} – {ms.get('max', 0):.1f}")
        print(f"  b-value estimate: {mag.get('b_value_estimate', 'N/A'):.3f}")

    # Dominant directions
    directions = summary.get('dominant_directions', [])
    if directions:
        print(f"\nMain Migration Directions:")
        for i, d in enumerate(directions, 1):
            print(f"  Direction {i}: {d['mean']:.1f}° ± {d['std']:.1f}°")


def print_directivity_summary(directivity_results):
    """Print directivity analysis summary using v4 API."""
    print("\n" + "=" * 50)
    print("DIRECTIVITY ANALYSIS RESULTS")
    print("=" * 50)

    stats = directivity_results.statistics
    print(f"Total event pairs: {stats.get('total_pairs', 'N/A')}")
    print(f"Mean directivity: {stats.get('mean_directivity', 0):.1f}°")
    print(f"Circular std: {stats.get('circular_std', 0):.1f}°")
    print(f"Resultant length: {stats.get('resultant_length', 0):.3f}")

    if len(directivity_results.gaussian_fits) > 0:
        print(f"\nGaussian fits:")
        for i, fit in enumerate(directivity_results.gaussian_fits, 1):
            print(f"  Fit {i}: mean={fit['mean']:.1f}°, std={fit['std']:.1f}°, amplitude={fit['amplitude']:.3f}")


def create_visualizations(events, directivity_results, analysis_result):
    """Create visualizations using v4 API."""
    from src.visualizer import plot_directivity_histogram, plot_polar_histogram, plot_epicenter_map

    try:
        plot_directivity_histogram(
            directivity_results,
            title="Directivity Distribution — Basic Example",
            save_filename="example_directivity_histogram.png"
        )
        plot_polar_histogram(
            directivity_results,
            title="Polar Distribution — Basic Example",
            save_filename="example_polar_histogram.png"
        )
        plot_epicenter_map(
            events,
            title="Earthquake Epicenters — Basic Example",
            save_filename="example_epicenter_map.png"
        )
        print("  Visualizations saved to figures/ directory")
    except Exception as e:
        print(f"  Visualization error: {e}")


if __name__ == "__main__":
    main()
