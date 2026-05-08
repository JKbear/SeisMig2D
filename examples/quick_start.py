#!/usr/bin/env python3
"""
Quick Start Example — SeisMig2D v4

Minimal example to get started with seismic migration analysis.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.catalog_reader import CatalogReaderFactory, EarthquakeEvent
from src.seismic_analyzer import calculate_directivities
import numpy as np
from datetime import datetime, timedelta


def main():
    print("SeisMig2D — Quick Start")
    print("=" * 50)

    # Step 1: Create simple synthetic data with a north-south migration pattern
    print("Creating synthetic data with north-south migration...")
    events = []
    base_time = datetime(2023, 1, 1)
    for i in range(50):
        event = EarthquakeEvent(
            time=base_time + timedelta(days=i * 1.2),
            latitude=35.0 + i * 0.04,       # migrates northward
            longitude=-118.0 + np.random.uniform(-0.05, 0.05),
            depth=10.0 + np.random.uniform(-3, 3),
            magnitude=2.5 + np.random.uniform(0, 1.5)
        )
        events.append(event)
    print(f"  Created {len(events)} synthetic events")

    # Step 2: Run directivity analysis
    print("\nRunning directivity analysis...")
    result = calculate_directivities(events, min_distance_km=1.0, max_distance_km=50.0)
    stats = result.statistics

    # Step 3: Print results
    print("\nResults:")
    print(f"  Total event pairs: {stats['total_pairs']}")
    print(f"  Mean directivity: {stats['mean_directivity']:.1f}°")
    print(f"  Circular std: {stats['circular_std']:.1f}°")
    print(f"  Resultant length: {stats['resultant_length']:.3f}")

    if result.gaussian_fits:
        print(f"\n  Detected migration directions:")
        for i, fit in enumerate(result.gaussian_fits, 1):
            print(f"    Direction {i}: {fit['mean']:.1f}° ± {fit['std']:.1f}°")

    # Step 4: Quick visualization
    try:
        from src.visualizer import plot_directivity_histogram
        plot_directivity_histogram(
            result,
            title="Quick Start — Directivity Distribution",
            save_filename="quickstart_directivity_histogram.png"
        )
        print("\n  Plot saved to figures/quickstart_directivity_histogram.png")
    except Exception as e:
        print(f"\n  Plot error: {e}")

    print("\nDone! Check the examples/ directory for more advanced usage.")


if __name__ == "__main__":
    main()
