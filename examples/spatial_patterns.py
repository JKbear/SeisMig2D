#!/usr/bin/env python3
"""
Spatial Pattern Analysis Example

Demonstrates spatial analysis features: clustering visualizations,
spatial density, depth distribution, and directional analysis by region.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.catalog_reader import CatalogReaderFactory, EarthquakeEvent
from src.seismic_analyzer import MigrationAnalyzer, calculate_directivities
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt


def main():
    print("Spatial Pattern Analysis")
    print("=" * 50)

    # Load or create data
    catalog_file = "../data/Case1_random_2faults.csv"
    if os.path.exists(catalog_file):
        print(f"Loading catalog: {catalog_file}")
        events = CatalogReaderFactory.read_catalog(catalog_file)
    else:
        print("Creating synthetic spatial data...")
        events = create_spatial_synthetic_data()

    print(f"Total events: {len(events)}")

    analyzer = MigrationAnalyzer()

    # Spatial statistics
    spatial = analyzer.spatial_analysis(events)
    sr = spatial.get('spatial_range', {})
    lat_stats = spatial.get('latitude_stats', {})
    lon_stats = spatial.get('longitude_stats', {})
    depth_stats = spatial.get('depth_stats', {})

    print("\n--- Spatial Statistics ---")
    print(f"  Latitude:  {lat_stats.get('min', 0):.3f} to {lat_stats.get('max', 0):.3f}  "
          f"(mean: {lat_stats.get('mean', 0):.3f}, std: {lat_stats.get('std', 0):.3f})")
    print(f"  Longitude: {lon_stats.get('min', 0):.3f} to {lon_stats.get('max', 0):.3f}  "
          f"(mean: {lon_stats.get('mean', 0):.3f}, std: {lon_stats.get('std', 0):.3f})")
    print(f"  Depth:     {depth_stats.get('min', 0):.1f} to {depth_stats.get('max', 0):.1f} km  "
          f"(mean: {depth_stats.get('mean', 0):.1f}, std: {depth_stats.get('std', 0):.1f})")
    print(f"  Spatial density: {spatial.get('spatial_density', 0):.4f} events/km^2")

    # Directional analysis for different regions
    lats = [e.latitude for e in events]
    median_lat = np.median(lats)
    south_events = [e for e in events if e.latitude < median_lat]
    north_events = [e for e in events if e.latitude >= median_lat]

    print("\n--- Directional Analysis by Region ---")
    for region_name, region_events in [("South", south_events), ("North", north_events)]:
        if len(region_events) >= 2:
            result = calculate_directivities(region_events, min_distance_km=0.5, max_distance_km=100)
            stats = result.statistics
            print(f"  {region_name} ({len(region_events)} events):")
            print(f"    Pairs: {stats['total_pairs']}, "
                  f"mean directivity: {stats['mean_directivity']:.1f}°, "
                  f"resultant length: {stats['resultant_length']:.3f}")
            if result.gaussian_fits:
                print(f"    Main direction: {result.gaussian_fits[0]['mean']:.1f}°")

    # Create spatial visualizations
    print("\n--- Creating Spatial Visualizations ---")
    try:
        from src.visualizer import plot_epicenter_map

        plot_epicenter_map(
            events,
            title="Earthquake Epicenters — Spatial Analysis",
            save_filename="spatial_epicenter_map.png"
        )
        print("  Epicenter map saved to figures/spatial_epicenter_map.png")

        # Depth distribution
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        depths = [e.depth for e in events]
        mags = [e.magnitude for e in events]

        ax1.hist(depths, bins=25, alpha=0.7, color='green', edgecolor='black')
        ax1.set_xlabel('Depth (km)')
        ax1.set_ylabel('Count')
        ax1.set_title('Depth Distribution')
        ax1.grid(True, alpha=0.3)

        ax2.scatter([e.longitude for e in events], [e.latitude for e in events],
                    c=mags, s=[(m - min(mags)) * 30 + 10 for m in mags],
                    cmap='Reds', alpha=0.6, edgecolors='black', linewidth=0.3)
        ax2.set_xlabel('Longitude')
        ax2.set_ylabel('Latitude')
        ax2.set_title('Spatial Distribution (color = magnitude)')
        ax2.grid(True, alpha=0.3)
        cbar = plt.colorbar(ax2.collections[0], ax=ax2)
        cbar.set_label('Magnitude')

        plt.tight_layout()
        os.makedirs("../figures", exist_ok=True)
        fig.savefig("../figures/spatial_patterns.png", dpi=150, bbox_inches='tight')
        print("  Spatial patterns plot saved to figures/spatial_patterns.png")
        plt.close(fig)
    except Exception as e:
        print(f"  Visualization error: {e}")

    print("\nSpatial analysis complete!")


def create_spatial_synthetic_data():
    """Create synthetic data with two spatial clusters and linear feature."""
    np.random.seed(42)
    events = []
    base_time = datetime(2022, 6, 1)

    # Cluster A: compact cluster in SW
    for i in range(60):
        events.append(EarthquakeEvent(
            time=base_time + timedelta(days=np.random.uniform(0, 60)),
            latitude=35.2 + np.random.normal(0, 0.08),
            longitude=-118.8 + np.random.normal(0, 0.08),
            depth=8 + np.random.normal(0, 2),
            magnitude=2.0 + np.random.exponential(0.5)
        ))

    # Cluster B: compact cluster in NE
    for i in range(50):
        events.append(EarthquakeEvent(
            time=base_time + timedelta(days=np.random.uniform(0, 60)),
            latitude=36.0 + np.random.normal(0, 0.06),
            longitude=-117.5 + np.random.normal(0, 0.06),
            depth=12 + np.random.normal(0, 3),
            magnitude=1.8 + np.random.exponential(0.5)
        ))

    # Linear feature between clusters (possible fault trace)
    for i in range(40):
        frac = i / 39
        events.append(EarthquakeEvent(
            time=base_time + timedelta(days=np.random.uniform(0, 60)),
            latitude=35.2 + frac * 0.8 + np.random.normal(0, 0.03),
            longitude=-118.8 + frac * 1.3 + np.random.normal(0, 0.03),
            depth=10 + np.random.normal(0, 2),
            magnitude=1.5 + np.random.exponential(0.4)
        ))

    return events


if __name__ == "__main__":
    main()
