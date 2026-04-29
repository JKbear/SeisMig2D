"""
Seismic Visualization Module

This module provides visualization functions for seismicity migration analysis,
including histograms, polar plots, time series plots, and interactive visualizations.
"""

import numpy as np
import pandas as pd
import logging
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Rectangle
from matplotlib.collections import LineCollection
from typing import List, Dict, Optional, Tuple, Any
import warnings
import os

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    go = None  # type: ignore
    px = None  # type: ignore
    make_subplots = None  # type: ignore
    warnings.warn("Plotly not available. Interactive visualizations will be disabled.")

from src.config import get_config
from src.catalog_reader import EarthquakeEvent
from src.seismic_analyzer import BearingAnalysisResult, MigrationAnalysisResult
from src.utils import get_color_mapper, get_coordinate_converter

# Get global configuration and tools
config = get_config()
color_mapper = get_color_mapper()
coordinate_converter = get_coordinate_converter()
logger = logging.getLogger(__name__)

class BaseVisualizer:
    """Base visualizer"""

    def __init__(self, figsize: Optional[Tuple[int, int]] = None, dpi: Optional[int] = None):
        """Initialize visualizer"""
        self.figsize = figsize or config.base.FIGURE_SIZE
        self.dpi = dpi or config.base.DPI
        self.color_palette: Dict[str, str] = config.visualization.COLORS

        try:
            plt.style.use('seaborn-v0_8')
        except Exception:
            try:
                plt.style.use('seaborn')
            except Exception:
                pass  # Fall back to default style
        plt.rcParams['figure.figsize'] = self.figsize
        plt.rcParams['figure.dpi'] = self.dpi
        plt.rcParams['font.size'] = config.base.FONT_SIZE

    def save_figure(self, fig: plt.Figure, filename: str, bbox_inches: str = 'tight', **kwargs: Any):
        """Save figure"""
        try:
            output_dir = config.base.FIGURE_DIR
            os.makedirs(output_dir, exist_ok=True)

            if '.' not in os.path.basename(filename):
                filename = f"{filename}.png"

            filepath = os.path.join(output_dir, filename)

            fig.savefig(filepath, bbox_inches=bbox_inches, **kwargs)
            logger.info(f"Figure saved: {filepath}")

        except Exception as e:
            logger.error(f"Failed to save figure: {e}")

    def close_figure(self, fig: plt.Figure):
        """Close figure"""
        plt.close(fig)

class BearingVisualizer(BaseVisualizer):
    """Bearing angle visualizer"""

    def _add_bearing_stats_box(self, ax: plt.Axes, statistics: Dict[str, Any]):
        """Helper to add statistics box to a bearing histogram."""
        stats_text = f"""
        Total pairs: {statistics.get('total_pairs', 'N/A')}
        Mean bearing: {statistics.get('mean_bearing', 0.0):.1f}°
        Std bearing: {statistics.get('std_bearing', 0.0):.1f}°
        """
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
               verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    def _add_polar_stats_box(self, fig: plt.Figure, statistics: Dict[str, Any]):
        """Helper to add statistics box to a polar plot."""
        stats_text = f"""
        Total pairs: {statistics.get('total_pairs', 'N/A')}
        Mean: {statistics.get('mean_bearing', 0.0):.1f}°
        Std: {statistics.get('std_bearing', 0.0):.1f}°
        """
        fig.text(0.5, 0.95, stats_text, transform=fig.transFigure,
               ha='center', va='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))


    def plot_bearing_histogram(self, analysis_result: BearingAnalysisResult,
                             title: str = "Bearing Distribution",
                             show_gaussian_fits: bool = True,
                             show_statistics: bool = True,
                             save_filename: Optional[str] = None,
                             ax: Optional[plt.Axes] = None) -> plt.Figure:
        """Plot bearing angle histogram"""
        if ax is None:
            fig, ax = plt.subplots(figsize=self.figsize)
        else:
            fig = ax.get_figure() # type: ignore

        bin_centers = analysis_result.bin_centers
        histogram = analysis_result.histogram

        bar_width = 360.0 / len(bin_centers)
        colors = [color_mapper.get_color(angle, config.base.COLOR_MAP) for angle in bin_centers]
        ax.bar(bin_centers, histogram, width=bar_width, color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)

        if show_gaussian_fits and analysis_result.gaussian_fits:
            x_smooth = np.linspace(0, 360, 1000)

            def gaussian(x: np.ndarray, amplitude: float, mean: float, std: float) -> np.ndarray:
                return amplitude * np.exp(-((x - mean) ** 2) / (2 * std ** 2))

            for i, fit in enumerate(analysis_result.gaussian_fits):
                y_smooth = gaussian(x_smooth, fit['amplitude'], fit['mean'], fit['std'])
                ax.plot(x_smooth, y_smooth, 'r-', linewidth=2,
                       label=f"Gaussian {i+1}: μ={fit['mean']:.1f}°, σ={fit['std']:.1f}°")
                ax.axvline(fit['mean'], color='red', linestyle='--', alpha=0.7)
                ax.text(fit['mean'], fit['amplitude'] * 1.1, f"{fit['mean']:.1f}°",
                       ha='center', va='bottom', fontsize=10, color='red')

        ax.set_xlabel('Bearing (degrees)', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlim(0, 360)
        ax.grid(True, alpha=0.3)

        if show_gaussian_fits and analysis_result.gaussian_fits:
            ax.legend(loc='upper right', fontsize=10)

        if show_statistics:
            self._add_bearing_stats_box(ax, analysis_result.statistics)

        plt.tight_layout()

        if save_filename:
            self.save_figure(fig, save_filename)

        return fig

    def plot_polar_histogram(self, analysis_result: BearingAnalysisResult,
                           title: str = "Polar Bearing Distribution",
                           show_statistics: bool = True,
                           save_filename: Optional[str] = None,
                           ax: Optional[plt.Axes] = None) -> plt.Figure:
        """Plot polar bearing angle histogram"""
        if ax is None:
            fig = plt.figure(figsize=(self.figsize[0], self.figsize[0]))
            ax = fig.add_subplot(111, projection='polar')
        else:
            fig = ax.get_figure() # type: ignore

        bin_centers_rad = np.radians(analysis_result.bin_centers)
        histogram = analysis_result.histogram

        n_bins = len(analysis_result.bin_centers)
        colors = [color_mapper.get_color(angle, config.base.COLOR_MAP) for angle in analysis_result.bin_centers]

        width = 2 * np.pi / n_bins
        ax.bar(bin_centers_rad, histogram, width=width, bottom=0.0,
               color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)

        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        ax.set_thetagrids(np.arange(0, 360, 30))

        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        if show_statistics:
            self._add_polar_stats_box(fig, analysis_result.statistics)

        plt.tight_layout()

        if save_filename:
            self.save_figure(fig, save_filename)

        return fig

    def plot_bearing_evolution(self, events: List[EarthquakeEvent],
                             time_window_days: int = 30,
                             title: str = "Bearing Evolution Over Time",
                             save_filename: Optional[str] = None) -> plt.Figure:
        """Plot bearing angle evolution over time"""
        events_with_time = sorted([e for e in events if e.time], key=lambda x: x.time)
        if len(events_with_time) < 2:
            raise ValueError("At least 2 earthquake events with time information are required")

        from datetime import datetime
        times: List[datetime] = []
        dominant_directions: List[float] = []
        event_counts: List[int] = []

        analyzer = BearingAnalyzer()
        for i, current_event in enumerate(events_with_time):
            window_start_ts = current_event.time.timestamp() - time_window_days * 24 * 3600
            window_events = [
                event for event in events_with_time
                if window_start_ts <= event.time.timestamp() <= current_event.time.timestamp()
            ]

            if len(window_events) >= 2:
                try:
                    result = analyzer.analyze_bearings(window_events)

                    if result.gaussian_fits:
                        dominant_direction = result.gaussian_fits[0]['mean']
                        times.append(current_event.time)
                        dominant_directions.append(dominant_direction)
                        event_counts.append(len(window_events))

                except ValueError:
                    continue

        if not times:
            raise ValueError("Not enough events in time window for analysis")

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(self.figsize[0], self.figsize[1] * 1.5), sharex=True)

        ax1.plot(times, dominant_directions, 'b-', linewidth=2, marker='o', markersize=4)
        ax1.set_ylabel('Dominant Direction (degrees)', fontsize=12)
        ax1.set_title(title, fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(0, 360)

        for direction in [0, 90, 180, 270]:
            ax1.axhline(direction, color='gray', linestyle='--', alpha=0.5)

        ax2.bar(times, event_counts, alpha=0.7, color='green', width=1)
        ax2.set_xlabel('Time', fontsize=12)
        ax2.set_ylabel('Event Count', fontsize=12)
        ax2.grid(True, alpha=0.3)

        fig.autofmt_xdate()
        plt.tight_layout()

        if save_filename:
            self.save_figure(fig, save_filename)

        return fig

class SeismicityVisualizer(BaseVisualizer):
    """Seismic activity visualizer"""

    def plot_epicenter_map(self, events: List[EarthquakeEvent],
                          title: str = "Earthquake Epicenters",
                          show_magnitude: bool = True,
                          color_by_time: bool = False,
                          save_filename: Optional[str] = None,
                          ax: Optional[plt.Axes] = None) -> plt.Figure:
        """Plot earthquake epicenter distribution"""
        if ax is None:
            fig, ax = plt.subplots(figsize=self.figsize)
        else:
            fig = ax.get_figure() # type: ignore

        if not events:
            logger.warning("No events to plot in plot_epicenter_map")
            ax.set_title(title)
            return fig

        lons = [e.longitude for e in events]
        lats = [e.latitude for e in events]
        mags = [e.magnitude for e in events]

        min_mag, max_mag = min(mags), max(mags)
        mag_range = max_mag - min_mag if max_mag > min_mag else 1.0

        def get_size(mag: float) -> float:
            return (mag - min_mag) / mag_range * 100 + 10

        colors: Any
        cmap: str
        cbar_label: str
        if color_by_time and any(e.time for e in events):
            times_ts = [e.time.timestamp() if e.time else 0 for e in events]
            colors = times_ts
            cmap = 'viridis'
            cbar_label = 'Time'
        else:
            colors = mags
            cmap = 'Reds'
            cbar_label = 'Magnitude'

        sizes = [get_size(m) for m in mags]

        scatter = ax.scatter(lons, lats, c=colors, s=sizes, cmap=cmap, alpha=0.7, edgecolors='black', linewidth=0.5)

        ax.set_xlabel('Longitude', fontsize=12)
        ax.set_ylabel('Latitude', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)

        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label(cbar_label, fontsize=12)

        if show_magnitude:
            mag_handles = []
            mag_levels = sorted(list(set([min_mag, np.mean(mags), max_mag])))
            for mag in mag_levels:
                mag_handles.append(ax.scatter([], [], c='gray', s=get_size(mag),
                                   alpha=0.7, edgecolors='black'))

            ax.legend(mag_handles,
                     [f'{mag:.1f}' for mag in mag_levels],
                     title='Magnitude', loc='upper right', fontsize=10, frameon=True)

        plt.tight_layout()

        if save_filename:
            self.save_figure(fig, save_filename)

        return fig

    def plot_magnitude_time_series(self, events: List[EarthquakeEvent],
                                 title: str = "Magnitude vs Time",
                                 save_filename: Optional[str] = None,
                                 ax: Optional[plt.Axes] = None) -> plt.Figure:
        """Plot magnitude time series"""
        events_with_time = sorted([e for e in events if e.time], key=lambda x: x.time)
        if not events_with_time:
            raise ValueError("No earthquake events with time information")

        times = [e.time for e in events_with_time]
        mags = [e.magnitude for e in events_with_time]

        if ax is None:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(self.figsize[0], self.figsize[1] * 1.2), sharex=True)
        else:
            fig = ax.get_figure() # type: ignore
            ax1 = ax
            ax2 = None

        ax1.scatter(times, mags, c=mags, cmap='Reds', s=30, alpha=0.7, edgecolors='black', linewidth=0.5)
        ax1.set_ylabel('Magnitude', fontsize=12)
        ax1.set_title(title, fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)

        if ax2 is not None:
            ax2.hist(mags, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
            ax2.set_xlabel('Time', fontsize=12)
            ax2.set_ylabel('Frequency', fontsize=12)
            ax2.grid(True, alpha=0.3)

        fig.autofmt_xdate()
        plt.tight_layout()

        if save_filename:
            self.save_figure(fig, save_filename)

        return fig

    def plot_depth_distribution(self, events: List[EarthquakeEvent],
                              title: str = "Depth Distribution",
                              save_filename: Optional[str] = None,
                              ax: Optional[plt.Axes] = None) -> plt.Figure:
        """Plot depth distribution"""
        depths = [e.depth for e in events]
        if not depths:
            logger.warning("No depth data to plot in plot_depth_distribution")
            if ax is None:
                fig, ax = plt.subplots(figsize=self.figsize)
            else:
                fig = ax.get_figure() # type: ignore
            ax.set_title(title)
            return fig

        if ax is None:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(self.figsize[0] * 1.2, self.figsize[1]))
        else:
            fig = ax.get_figure() # type: ignore
            ax1 = ax
            ax2 = None

        ax1.hist(depths, bins=30, alpha=0.7, color='green', edgecolor='black')
        ax1.set_xlabel('Depth (km)', fontsize=12)
        ax1.set_ylabel('Frequency', fontsize=12)
        ax1.set_title(f'{title} - Histogram', fontsize=12)
        ax1.grid(True, alpha=0.3)

        if ax2 is not None:
            ax2.boxplot(depths, vert=True, patch_artist=True,
                       boxprops=dict(facecolor='lightgreen', alpha=0.7))
            ax2.set_ylabel('Depth (km)', fontsize=12)
            ax2.set_title(f'{title} - Boxplot', fontsize=12)
            ax2.grid(True, alpha=0.3)

            stats_text = f"""
            Mean: {np.mean(depths):.1f} km
            Median: {np.median(depths):.1f} km
            Std: {np.std(depths):.1f} km
            Min: {np.min(depths):.1f} km
            Max: {np.max(depths):.1f} km
            """
            ax2.text(0.02, 0.98, stats_text, transform=ax2.transAxes,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        plt.tight_layout()

        if save_filename:
            self.save_figure(fig, save_filename)

        return fig

class InteractiveVisualizer:
    """Interactive visualizer (requires plotly)"""

    def __init__(self):
        """Initialize interactive visualizer"""
        if not PLOTLY_AVAILABLE:
            raise ImportError("plotly library is required for interactive visualization features")

    def create_interactive_map(self, events: List[EarthquakeEvent],
                             title: str = "Interactive Earthquake Map") -> "go.Figure":
        """Create interactive earthquake epicenter map"""
        if not events:
            logger.warning("No events to plot in create_interactive_map")
            import plotly.graph_objects as go
            return go.Figure()

        lons = [e.longitude for e in events]
        lats = [e.latitude for e in events]
        mags = [e.magnitude for e in events]
        depths = [e.depth for e in events]
        times = [str(e.time) if e.time else 'Unknown' for e in events]

        min_mag, max_mag = min(mags), max(mags)
        mag_range = max_mag - min_mag if max_mag > min_mag else 1.0
        sizes = [(mag - min_mag) / mag_range * 20 + 5 for mag in mags]

        fig = go.Figure(data=go.Scattergeo(
            lon=lons,
            lat=lats,
            mode='markers',
            marker=dict(
                size=sizes,
                color=mags,
                colorscale='Reds',
                showscale=True,
                colorbar=dict(title="Magnitude")
            ),
            text=[f"Mag: {mag:.2f}<br>Depth: {depth:.1f} km<br>Time: {time}"
                  for mag, depth, time in zip(mags, depths, times)],
            hovertemplate='<b>Earthquake</b><br>%{text}<br>Lat: %{lat}<br>Lon: %{lon}<extra></extra>'
        ))

        fig.update_layout(
            title=title,
            geo=dict(
                projection_type='natural earth',
                showland=True,
                landcolor='rgb(243, 243, 243)',
                coastlinecolor='rgb(204, 204, 204)',
            )
        )
        return fig

    def create_interactive_histogram(self, analysis_result: BearingAnalysisResult,
                                   title: str = "Interactive Bearing Histogram") -> "go.Figure":
        """Create interactive bearing histogram"""
        import plotly.graph_objects as go

        bin_centers = analysis_result.bin_centers
        histogram = analysis_result.histogram

        fig = go.Figure(data=[go.Bar(
            x=bin_centers,
            y=histogram,
            marker_color=[color_mapper.get_color(angle, config.base.COLOR_MAP) for angle in bin_centers],
            hovertemplate='<b>Bearing: %{x:.1f}°</b><br>Frequency: %{y}<extra></extra>'
        )])

        if analysis_result.gaussian_fits:
            x_smooth = np.linspace(0, 360, 1000)

            def gaussian(x: np.ndarray, amplitude: float, mean: float, std: float) -> np.ndarray:
                return amplitude * np.exp(-((x - mean) ** 2) / (2 * std ** 2))

            for i, fit in enumerate(analysis_result.gaussian_fits):
                y_smooth = gaussian(x_smooth, fit['amplitude'], fit['mean'], fit['std'])

                fig.add_trace(go.Scatter(
                    x=x_smooth,
                    y=y_smooth,
                    mode='lines',
                    name=f"Gaussian {i+1}: μ={fit['mean']:.1f}°, σ={fit['std']:.1f}°",
                    line=dict(color='red', width=2)
                ))

        fig.update_layout(
            title=title,
            xaxis_title="Bearing (degrees)",
            yaxis_title="Frequency",
            showlegend=bool(analysis_result.gaussian_fits)
        )
        return fig

class ComprehensiveVisualizer(BaseVisualizer):
    """Comprehensive analysis visualizer"""

    def __init__(self):
        """Initialize comprehensive analysis visualizer"""
        super().__init__()
        self.bearing_viz = BearingVisualizer()
        self.seismicity_viz = SeismicityVisualizer()

        if PLOTLY_AVAILABLE:
            self.interactive_viz = InteractiveVisualizer()

    def create_analysis_dashboard(self, events: List[EarthquakeEvent],
                                analysis_result: MigrationAnalysisResult,
                                title: str = "Seismicity Migration Analysis Dashboard",
                                save_filename: Optional[str] = None) -> plt.Figure:
        """Create analysis dashboard"""
        fig = plt.figure(figsize=(20, 16))
        gs = fig.add_gridspec(4, 3, hspace=0.4, wspace=0.3)

        # 1. Epicenter distribution map
        ax1 = fig.add_subplot(gs[0, :2])
        self.seismicity_viz.plot_epicenter_map(events, title="Earthquake Epicenters", ax=ax1)

        # 2. Magnitude time series
        ax2_main = fig.add_subplot(gs[0, 2])
        try:
            events_with_time = sorted([e for e in events if e.time], key=lambda x: x.time)
            if not events_with_time:
                raise ValueError("No events with time data")
            times = [e.time for e in events_with_time]
            mags = [e.magnitude for e in events_with_time]

            ax2_main.scatter(times, mags, c=mags, cmap='Reds', s=20, alpha=0.7)
            ax2_main.set_ylabel('Magnitude')
            ax2_main.set_title('Magnitude vs Time')
            ax2_main.grid(True, alpha=0.3)
            fig.autofmt_xdate(bottom=0.2, rotation=30, ha='right')

        except ValueError as e:
            ax2_main.text(0.5, 0.5, str(e), ha='center', va='center', wrap=True)
            ax2_main.set_title("Magnitude vs Time")

        # 3. Bearing histogram
        ax3 = fig.add_subplot(gs[1, :])
        self.bearing_viz.plot_bearing_histogram(
            analysis_result.directional_analysis,
            title="Bearing Distribution with Gaussian Fits",
            show_statistics=False,
            ax=ax3
        )

        # 4. Polar plot
        ax4 = fig.add_subplot(gs[2, 0], projection='polar')
        self.bearing_viz.plot_polar_histogram(
            analysis_result.directional_analysis,
            title="Polar Bearing",
            show_statistics=False,
            ax=ax4
        )

        # 5. Depth distribution
        ax5 = fig.add_subplot(gs[2, 1])
        depths = [e.depth for e in events]
        if depths:
            ax5.hist(depths, bins=20, alpha=0.7, color='green', edgecolor='black')
        ax5.set_xlabel('Depth (km)')
        ax5.set_ylabel('Frequency')
        ax5.set_title('Depth Distribution')
        ax5.grid(True, alpha=0.3)

        # 6. Magnitude distribution
        ax6 = fig.add_subplot(gs[2, 2])
        mags = [e.magnitude for e in events]
        if mags:
            ax6.hist(mags, bins=20, alpha=0.7, color='orange', edgecolor='black')
        ax6.set_xlabel('Magnitude')
        ax6.set_ylabel('Frequency')
        ax6.set_title('Magnitude Distribution')
        ax6.grid(True, alpha=0.3)

        # 7. Statistics information
        ax7 = fig.add_subplot(gs[3, :])
        ax7.axis('off')

        stats_text = f"""
        ANALYSIS SUMMARY
        Total Events: {analysis_result.summary_statistics.get('total_events', 'N/A')}
        Total Pairs: {analysis_result.directional_analysis.statistics.get('total_pairs', 'N/A')}

        DOMINANT DIRECTIONS:
        """
        dominant_directions = analysis_result.summary_statistics.get('dominant_directions', [])
        if dominant_directions:
            for i, direction in enumerate(dominant_directions):
                stats_text += f"\nDirection {i+1}: {direction.get('mean', 0.0):.1f}° ± {direction.get('std', 0.0):.1f}°"
        else:
            stats_text += "\nNo dominant directions found."

        stats_text += f"""

        SPATIAL ANALYSIS:
        Latitude Range: {analysis_result.spatial_analysis.get('spatial_range', {}).get('latitude_range', 0.0):.2f}°
        Longitude Range: {analysis_result.spatial_analysis.get('spatial_range', {}).get('longitude_range', 0.0):.2f}°
        Spatial Density: {analysis_result.spatial_analysis.get('spatial_density', 0.0):.2f} events/km²

        MAGNITUDE ANALYSIS:
        Mean Magnitude: {analysis_result.magnitude_analysis.get('magnitude_stats', {}).get('mean', 0.0):.2f}
        b-value Estimate: {analysis_result.magnitude_analysis.get('b_value_estimate', 0.0):.2f}
        """

        ax7.text(0.05, 0.95, stats_text, transform=ax7.transAxes,
                verticalalignment='top', fontsize=12,
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8),
                family='monospace')

        fig.suptitle(title, fontsize=16, fontweight='bold', y=0.98)

        if save_filename:
            self.save_figure(fig, save_filename)

        return fig

# Convenience functions
def plot_bearing_histogram(analysis_result: BearingAnalysisResult, **kwargs: Any) -> plt.Figure:
    """Plot bearing histogram (convenience function)"""
    viz = BearingVisualizer()
    return viz.plot_bearing_histogram(analysis_result, **kwargs)

def plot_polar_histogram(analysis_result: BearingAnalysisResult, **kwargs: Any) -> plt.Figure:
    """Plot polar histogram (convenience function)"""
    viz = BearingVisualizer()
    return viz.plot_polar_histogram(analysis_result, **kwargs)

def plot_epicenter_map(events: List[EarthquakeEvent], **kwargs: Any) -> plt.Figure:
    """Plot epicenter map (convenience function)"""
    viz = SeismicityVisualizer()
    return viz.plot_epicenter_map(events, **kwargs)

def create_analysis_dashboard(events: List[EarthquakeEvent], analysis_result: MigrationAnalysisResult, **kwargs: Any) -> plt.Figure:
    """Create analysis dashboard (convenience function)"""
    viz = ComprehensiveVisualizer()
    return viz.create_analysis_dashboard(events, analysis_result, **kwargs)
