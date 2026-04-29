#!/usr/bin/env python3
"""
Temporal Evolution Analysis Example

Demonstrates how to analyze temporal evolution of seismic migration patterns
using sliding time windows and the MigrationAnalyzer.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.catalog_reader import CatalogReaderFactory, EarthquakeEvent
from src.seismic_analyzer import MigrationAnalyzer
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt


def main():
    print("Temporal Evolution Analysis")
    print("=" * 50)

    # Load or create data
    catalog_file = "../data/Wenchuan_hypoDD.reloc_ChenJiuhui09.txt"
    if os.path.exists(catalog_file):
        print(f"Loading catalog: {catalog_file}")
        events = CatalogReaderFactory.read_catalog(catalog_file)
    else:
        print("Creating synthetic temporal data...")
        events = create_temporal_synthetic_data()

    # Sort by time
    events = sorted([e for e in events if e.time], key=lambda x: x.time)
    print(f"Events with time: {len(events)}")
    print(f"Time range: {events[0].time} to {events[-1].time}")

    analyzer = MigrationAnalyzer()

    # Temporal analysis with different windows
    print("\n--- Sliding Window Analysis ---")
    for window_days in [7, 30, 90]:
        temporal = analyzer.temporal_analysis(events, time_window_days=window_days)
        windows = temporal.get('window_analysis', [])

        directions = [w['dominant_direction'] for w in windows if w['dominant_direction'] is not None]
        if directions:
            print(f"  {window_days:2d}-day window: {len(windows)} windows, "
                  f"direction mean={np.mean(directions):.1f}°, std={np.std(directions):.1f}°")

    # Time series statistics
    ts_stats = temporal.get('time_series_stats', {})
    mag_stats = temporal.get('magnitude_stats', {})
    print(f"\n--- Time Series Statistics ---")
    print(f"  Mean inter-event time: {ts_stats.get('mean', 0):.1f} hours")
    print(f"  Total duration: {ts_stats.get('total_duration_days', 0):.1f} days")
    print(f"  Mean magnitude: {mag_stats.get('mean', 0):.2f}")

    # Plot temporal evolution of dominant direction
    print("\n--- Creating Temporal Evolution Plot ---")
    try:
        windows = temporal.get('window_analysis', [])
        if len(windows) > 2:
            times = [w['time'] for w in windows]
            directions = [w['dominant_direction'] if w['dominant_direction'] is not None else np.nan
                          for w in windows]
            counts = [w['event_count'] for w in windows]

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
            ax1.plot(times, directions, 'b-o', markersize=4)
            ax1.set_ylabel('Dominant Direction (°)')
            ax1.set_ylim(0, 360)
            ax1.grid(True, alpha=0.3)
            for d in [0, 90, 180, 270]:
                ax1.axhline(d, color='gray', linestyle='--', alpha=0.5)
            ax1.set_title('Temporal Evolution of Migration Direction')

            ax2.bar(times, counts, alpha=0.7, color='green')
            ax2.set_ylabel('Events in Window')
            ax2.set_xlabel('Time')
            ax2.grid(True, alpha=0.3)

            fig.autofmt_xdate()
            plt.tight_layout()
            os.makedirs("../figures", exist_ok=True)
            fig.savefig("../figures/temporal_evolution.png", dpi=150, bbox_inches='tight')
            print("  Plot saved to figures/temporal_evolution.png")
            plt.close(fig)
    except Exception as e:
        print(f"  Plot error: {e}")

    print("\nTemporal analysis complete!")


def create_temporal_synthetic_data():
    """Create synthetic data with clear temporal migration pattern."""
    np.random.seed(42)
    events = []
    base_time = datetime(2022, 1, 1)

    # Phase 1: Days 0-30, SW cluster
    for i in range(30):
        events.append(EarthquakeEvent(
            time=base_time + timedelta(days=np.random.uniform(0, 30)),
            latitude=35.0 + np.random.uniform(-0.1, 0.1),
            longitude=-118.5 + np.random.uniform(-0.1, 0.1),
            depth=np.random.uniform(5, 15),
            magnitude=2.0 + np.random.uniform(0, 1.5)
        ))

    # Phase 2: Days 30-60, migrating NE
    for i in range(40):
        frac = i / 39
        events.append(EarthquakeEvent(
            time=base_time + timedelta(days=30 + np.random.uniform(0, 30)),
            latitude=35.0 + frac * 1.0 + np.random.uniform(-0.1, 0.1),
            longitude=-118.5 + frac * 1.0 + np.random.uniform(-0.1, 0.1),
            depth=np.random.uniform(5, 15),
            magnitude=2.0 + np.random.uniform(0, 1.5)
        ))

    # Phase 3: Days 60-90, NE cluster
    for i in range(30):
        events.append(EarthquakeEvent(
            time=base_time + timedelta(days=60 + np.random.uniform(0, 30)),
            latitude=36.0 + np.random.uniform(-0.1, 0.1),
            longitude=-117.5 + np.random.uniform(-0.1, 0.1),
            depth=np.random.uniform(5, 15),
            magnitude=2.0 + np.random.uniform(0, 1.5)
        ))

    return events


if __name__ == "__main__":
    main()
