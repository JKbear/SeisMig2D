#!/usr/bin/env python3
"""
Interactive Visualization Demo

Demonstrates interactive Plotly visualizations for seismic migration analysis.
Requires: pip install plotly
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.catalog_reader import CatalogReaderFactory, EarthquakeEvent
from src.seismic_analyzer import calculate_directivities
import numpy as np
from datetime import datetime, timedelta


def main():
    print("Interactive Visualization Demo")
    print("=" * 50)

    # Check plotly availability
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("Plotly is not installed. Run: pip install plotly")
        print("Falling back to static matplotlib output...")
        run_static_demo()
        return

    # Create synthetic data
    print("Creating synthetic data...")
    events = create_synthetic_data()
    print(f"  Created {len(events)} events")

    # Run directivity analysis
    print("Running directivity analysis...")
    directivity_result = calculate_directivities(events, min_distance_km=1.0, max_distance_km=100.0)
    print(f"  {directivity_result.statistics['total_pairs']} event pairs")

    # Create interactive map
    print("\n--- Interactive Epicenter Map ---")
    lons = [e.longitude for e in events]
    lats = [e.latitude for e in events]
    mags = [e.magnitude for e in events]
    depths = [e.depth for e in events]
    times = [str(e.time) if e.time else 'Unknown' for e in events]

    sizes = [(m - min(mags)) / (max(mags) - min(mags)) * 20 + 5 for m in mags]

    fig_map = go.Figure(data=go.Scattergeo(
        lon=lons, lat=lats, mode='markers',
        marker=dict(size=sizes, color=mags, colorscale='Reds',
                    showscale=True, colorbar=dict(title="Magnitude")),
        text=[f"Mag: {m:.2f}<br>Depth: {d:.1f} km<br>Time: {t}"
              for m, d, t in zip(mags, depths, times)],
        hovertemplate='<b>Earthquake</b><br>%{text}<extra></extra>'
    ))
    fig_map.update_layout(
        title="Interactive Earthquake Map",
        geo=dict(projection_type='natural earth', showland=True,
                 landcolor='rgb(243, 243, 243)', coastlinecolor='rgb(204, 204, 204)')
    )
    os.makedirs("../figures", exist_ok=True)
    fig_map.write_html("../figures/interactive_map.html")
    print("  Saved to figures/interactive_map.html")

    # Create interactive directivity histogram
    print("\n--- Interactive Directivity Histogram ---")
    bin_centers = directivity_result.bin_centers
    histogram = directivity_result.histogram

    fig_hist = go.Figure(data=[go.Bar(
        x=bin_centers, y=histogram,
        hovertemplate='<b>Directivity: %{x:.1f}°</b><br>Frequency: %{y}<extra></extra>'
    )])

    # Add Gaussian fits
    for i, fit in enumerate(directivity_result.gaussian_fits):
        x_smooth = np.linspace(0, 360, 1000)
        y_smooth = fit['amplitude'] * np.exp(-((x_smooth - fit['mean']) ** 2) / (2 * fit['std'] ** 2))
        fig_hist.add_trace(go.Scatter(
            x=x_smooth, y=y_smooth, mode='lines',
            name=f"Direction {i+1}: {fit['mean']:.1f}° ± {fit['std']:.1f}°",
            line=dict(color='red', width=2)
        ))

    fig_hist.update_layout(
        title="Interactive Directivity Distribution",
        xaxis_title="Directivity (degrees)",
        yaxis_title="Frequency",
        showlegend=True
    )
    fig_hist.write_html("../figures/interactive_histogram.html")
    print("  Saved to figures/interactive_histogram.html")

    print("\nOpen the HTML files in a browser to explore the interactive visualizations.")


def run_static_demo():
    """Fallback to static matplotlib visualizations."""
    from src.visualizer import plot_directivity_histogram, plot_epicenter_map
    from src.seismic_analyzer import calculate_directivities

    events = create_synthetic_data()
    directivity_result = calculate_directivities(events, min_distance_km=1.0, max_distance_km=100.0)

    plot_epicenter_map(events, title="Earthquake Epicenters",
                       save_filename="interactive_demo_epicenter_map.png")
    plot_directivity_histogram(directivity_result, title="Directivity Distribution",
                           save_filename="interactive_demo_directivity_histogram.png")
    print("  Static plots saved to figures/ directory")


def create_synthetic_data():
    """Create synthetic earthquake data with clear migration."""
    np.random.seed(42)
    events = []
    base_time = datetime(2022, 1, 1)

    for i in range(100):
        frac = i / 99
        events.append(EarthquakeEvent(
            time=base_time + timedelta(days=i * 0.5),
            latitude=35.0 + frac * 1.0 + np.random.normal(0, 0.05),
            longitude=-118.0 + frac * 1.5 + np.random.normal(0, 0.05),
            depth=10.0 + np.random.normal(0, 3),
            magnitude=2.0 + np.random.exponential(0.6)
        ))

    return events


if __name__ == "__main__":
    main()
