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
from datetime import datetime
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
from src.seismic_analyzer import DirectivityAnalysisResult, MigrationAnalysisResult, DirectivityAnalyzer, TemporalDirectivityResult
from src.utils import get_color_mapper, get_coordinate_converter

# Get global configuration and tools
config = get_config()
color_mapper = get_color_mapper()
coordinate_converter = get_coordinate_converter()
logger = logging.getLogger(__name__)

# --- Nature-figure publication rcParams ---
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none",     # editable text in SVG
    "pdf.fonttype": 42,         # editable TrueType text in PDF
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 0.8,
    "legend.frameon": False,
})


def save_pub_py(fig: plt.Figure, filepath_base: str, dpi: int = 600,
                formats: Optional[List[str]] = None):
    """Save figure in publication-ready formats (SVG, PDF, TIFF).

    Parameters
    ----------
    fig : matplotlib Figure
    filepath_base : path WITHOUT extension (e.g. 'figures/figure1')
    dpi : raster DPI (used for TIFF)
    formats : list of extensions, default ['svg', 'pdf', 'tiff']
    """
    if formats is None:
        formats = config.base.EXPORT_FORMATS
    os.makedirs(os.path.dirname(filepath_base) or '.', exist_ok=True)
    for fmt in formats:
        if fmt == 'tiff':
            fig.savefig(f"{filepath_base}.tiff", dpi=dpi, bbox_inches="tight")
        elif fmt == 'svg':
            fig.savefig(f"{filepath_base}.svg", bbox_inches="tight")
        elif fmt == 'pdf':
            fig.savefig(f"{filepath_base}.pdf", bbox_inches="tight")
        else:
            fig.savefig(f"{filepath_base}.{fmt}", dpi=dpi, bbox_inches="tight")
    logger.info(f"Figure saved: {filepath_base}.{{{', '.join(formats)}}}")


def _add_direction_colorbar(ax: plt.Axes, cmap_name: str, vmin: float = 0,
                            vmax: float = 360, label: str = "Direction (degrees)",
                            orientation: str = "vertical", **kwargs):
    """Add a standardised direction colorbar.

    Extracted to eliminate duplicated colorbar code across plot methods.
    """
    sm = plt.cm.ScalarMappable(cmap=cmap_name, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, label=label, orientation=orientation, **kwargs)
    cbar.set_ticks(np.linspace(vmin, vmax, num=5))
    cbar.set_ticklabels([f'{int(x)}\u00b0' for x in np.linspace(vmin, vmax, num=5)])
    cbar.outline.set_color('black')
    cbar.outline.set_linewidth(0.5)
    return cbar


def _gaussian(x: np.ndarray, amplitude: float, mean: float, std: float) -> np.ndarray:
    """Gaussian function — kept for backward compatibility."""
    return amplitude * np.exp(-((x - mean) ** 2) / (2 * std ** 2))


def _vonmises_curve(x: np.ndarray, amplitude: float, mean: float,
                    kappa: float) -> np.ndarray:
    """Von Mises curve scaled to histogram counts. x in degrees."""
    # Normalised von Mises without I₀: peak = amplitude at x=mean
    return amplitude * np.exp(kappa * (np.cos(np.radians(x - mean)) - 1.0))


class BaseVisualizer:
    """Base visualizer"""

    def __init__(self, figsize: Optional[Tuple[int, int]] = None, dpi: Optional[int] = None,
                 output_dir: str = ""):
        """Initialize visualizer

        Parameters
        ----------
        output_dir : directory for save_figure; falls back to config FIGURE_DIR.
        """
        self.figsize = figsize or config.base.FIGURE_SIZE
        self.dpi = dpi or config.base.DPI
        self.color_palette: Dict[str, str] = config.visualization.COLORS
        self.output_dir = output_dir

    def save_figure(self, fig: plt.Figure, filename: str, output_dir: Optional[str] = None,
                    bbox_inches: str = 'tight', **kwargs: Any):
        """Save figure. Uses output_dir arg > self.output_dir > config FIGURE_DIR."""
        try:
            target_dir = output_dir or self.output_dir or config.base.FIGURE_DIR
            os.makedirs(target_dir, exist_ok=True)

            filepath = os.path.join(target_dir, filename)
            fig.savefig(filepath, bbox_inches=bbox_inches, **kwargs)
            logger.info(f"Figure saved: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to save figure: {e}")
            return None

    def save_figure_pub(self, fig: plt.Figure, filepath_base: str,
                        dpi: int = 600, formats: Optional[List[str]] = None):
        """Save in publication formats via save_pub_py.

        Parameters
        ----------
        filepath_base : path WITHOUT extension
        """
        save_pub_py(fig, filepath_base, dpi=dpi, formats=formats)

    def close_figure(self, fig: plt.Figure):
        """Close figure"""
        plt.close(fig)

class DirectivityVisualizer(BaseVisualizer):
    """Directivity angle visualizer"""

    def plot_directivity_histogram(self, analysis_result: DirectivityAnalysisResult,
                             title: str = "Directivity Distribution",
                             show_gaussian_fits: bool = True,
                             save_filename: Optional[str] = None,
                             ax: Optional[plt.Axes] = None) -> plt.Figure:
        """Plot directivity angle histogram"""
        if ax is None:
            fig, ax = plt.subplots(figsize=self.figsize)
        else:
            fig = ax.get_figure() # type: ignore

        bin_centers = analysis_result.bin_centers
        histogram = analysis_result.histogram
        cmap_name = config.base.COLOR_MAP

        bar_width = 360.0 / len(bin_centers)
        colors = [color_mapper.get_color(angle, cmap_name) for angle in bin_centers]
        ax.bar(bin_centers, histogram, width=bar_width, color=colors, alpha=0.7,
               edgecolor='k', linewidth=0.5, label='Histogram')

        # Detected peaks as black dots
        if len(analysis_result.peaks) > 0:
            peak_centers = bin_centers[analysis_result.peaks]
            peak_heights = histogram[analysis_result.peaks]
            ax.plot(peak_centers, peak_heights, 'ko', markersize=5, label='Detected Peaks')

        if show_gaussian_fits and analysis_result.gaussian_fits:
            x_smooth = np.linspace(0, 360, 1000)

            for i, fit in enumerate(analysis_result.gaussian_fits):
                if 'kappa' in fit:
                    y_smooth = _vonmises_curve(x_smooth, fit['amplitude'], fit['mean'], fit['kappa'])
                else:
                    y_smooth = _gaussian(x_smooth, fit['amplitude'], fit['mean'], fit['std'])
                gauss_label = 'Fitted Gaussian Curves' if i == 0 else None
                ax.plot(x_smooth, y_smooth, color='red', linestyle='--', linewidth=2,
                       label=gauss_label)
                # Annotate near peak
                peak_y = fit['amplitude']
                # First peak(s) near left edge → annotate on right;
                # later peaks → annotate on left to avoid legend overlap
                if fit['mean'] > 100:
                    text_x = fit['mean'] - 40
                else:
                    text_x = fit['mean'] + 5
                ax.text(text_x, peak_y,
                       f'Mean: {fit["mean"]:.0f}°\nStd: {fit["std"]:.2f}',
                       verticalalignment='center', horizontalalignment='left', fontsize=9, linespacing=1.6)

        ax.set_xlabel('Direction from the East (degree)', fontsize=12)
        ax.set_ylabel('Number of Earthquake Pairs', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlim(0, 360)
        ax.grid(True, alpha=0.3, color='gray', linestyle='--')

        ax.legend(loc='upper right')

        _add_direction_colorbar(ax, cmap_name)

        plt.tight_layout()

        if save_filename:
            self.save_figure(fig, save_filename)

        return fig

    def plot_polar_histogram(self, analysis_result: DirectivityAnalysisResult,
                           title: str = "Polar Directivity Distribution",
                           save_filename: Optional[str] = None,
                           ax: Optional[plt.Axes] = None) -> plt.Figure:
        """Plot polar directivity angle histogram"""
        if ax is None:
            fig = plt.figure(figsize=(self.figsize[0], self.figsize[0]))
            ax = fig.add_subplot(111, projection='polar')
        else:
            fig = ax.get_figure() # type: ignore

        bin_centers = analysis_result.bin_centers
        histogram = analysis_result.histogram
        cmap_name = config.base.COLOR_MAP

        n_bins = len(bin_centers)
        bin_centers_rad = np.radians(bin_centers)
        width = 2 * np.pi / n_bins
        colors = [color_mapper.get_color(angle, cmap_name) for angle in bin_centers]

        bars = ax.bar(bin_centers_rad, histogram, width=width, bottom=0.0,
                      color=colors, alpha=0.7, edgecolor='k', linewidth=0.5)

        # Grid: thin dashed lines
        ax.grid(True, linestyle='--', alpha=0.7, linewidth=0.5)

        # East as zero, clockwise
        ax.set_theta_zero_location('E')
        ax.set_theta_direction(1)

        # Cardinal direction labels at edge (below title)
        rmax = ax.get_rmax()
        ax.text(0, rmax * 1.12, 'E', ha='center', va='center', fontsize=12, fontweight='bold')
        ax.text(np.pi / 2, rmax * 1.14, 'N', ha='center', va='center', fontsize=12, fontweight='bold')
        ax.text(np.pi, rmax * 1.17, 'W', ha='center', va='center', fontsize=12, fontweight='bold')
        ax.text(3 * np.pi / 2, rmax * 1.12, 'S', ha='center', va='center', fontsize=12, fontweight='bold')

        # ax.set_title(title, fontsize=14, fontweight='bold', pad=28)

        # von Mises mixture fits: red dashed curves with annotations
        if analysis_result.gaussian_fits:
            x_range = np.linspace(0, 2 * np.pi, 1000)
            x_deg = np.degrees(x_range)
            for fit in analysis_result.gaussian_fits:
                if 'kappa' in fit:
                    fitted_curve = _vonmises_curve(x_deg, fit['amplitude'], fit['mean'], fit['kappa'])
                else:
                    fitted_curve = _gaussian(x_deg, fit['amplitude'], fit['mean'], fit['std'])
                ax.plot(x_range, fitted_curve, 'r--', linewidth=2)
                ax.text(np.radians(fit['mean']), ax.get_ylim()[1] * 0.85,
                       f'Mean: {fit["mean"]:.0f}°\nStd: {fit["std"]:.2f}',
                       ha='center', va='bottom', fontsize=9, color='black', linespacing=1.6)

        # Colorbar
        _add_direction_colorbar(ax, cmap_name, pad=0.1, shrink=0.5)

        plt.tight_layout()

        if save_filename:
            self.save_figure(fig, save_filename)

        return fig

    def plot_directivity_evolution(self,
                             window_analysis: Optional[List[Dict[str, Any]]] = None,
                             events: Optional[List[EarthquakeEvent]] = None,
                             time_window_days: int = 30,
                             title: str = "Directivity Evolution Over Time",
                             save_filename: Optional[str] = None) -> plt.Figure:
        """Plot directivity angle evolution over time.

        Prefer passing window_analysis (from MigrationAnalysisResult) to
        avoid recomputing sliding windows. Falls back to events for
        backwards compatibility.
        """
        if window_analysis:
            times = [w['time'] for w in window_analysis]
            dominant_directions = [w['dominant_direction'] for w in window_analysis
                                   if w['dominant_direction'] is not None]
            event_counts = [w['event_count'] for w in window_analysis]
            # Re-align after filtering None directions
            valid_indices = [i for i, w in enumerate(window_analysis)
                           if w['dominant_direction'] is not None]
            times = [times[i] for i in valid_indices]
            event_counts = [event_counts[i] for i in valid_indices]
        elif events:
            events_with_time = sorted([e for e in events if e.time], key=lambda x: x.time)
            if len(events_with_time) < 2:
                raise ValueError("At least 2 earthquake events with time information are required")

            """  # noqa — module-level import above"""
            times_dt: List[datetime] = []
            dominant_directions_dt: List[float] = []
            event_counts_dt: List[int] = []

            analyzer = DirectivityAnalyzer()
            for i, current_event in enumerate(events_with_time):
                window_start_ts = current_event.time.timestamp() - time_window_days * 24 * 3600
                window_events = [
                    event for event in events_with_time
                    if window_start_ts <= event.time.timestamp() <= current_event.time.timestamp()
                ]
                if len(window_events) >= 2:
                    try:
                        result = analyzer.analyze_directivities(window_events)
                        if result.gaussian_fits:
                            dominant_direction_dt = result.gaussian_fits[0]['mean']
                            times_dt.append(current_event.time)
                            dominant_directions_dt.append(dominant_direction_dt)
                            event_counts_dt.append(len(window_events))
                    except ValueError:
                        continue
            times = times_dt
            dominant_directions = dominant_directions_dt
            event_counts = event_counts_dt
        else:
            raise ValueError("Provide window_analysis or events")

        if not times:
            raise ValueError("Not enough data for evolution plot")

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

    def plot_histogram_with_peak_regions(self,
                                          analysis_result: DirectivityAnalysisResult,
                                          peak_half_width: float = 30,
                                          title: str = "Directivity Distribution with Peak Regions",
                                          save_filename: Optional[str] = None,
                                          ax: Optional[plt.Axes] = None) -> plt.Figure:
        """Plot directivity histogram with peak region highlights and N2/N1 ratio."""
        if ax is None:
            fig, ax = plt.subplots(figsize=self.figsize)
        else:
            fig = ax.get_figure() # type: ignore

        bin_centers = analysis_result.bin_centers
        histogram = analysis_result.histogram
        cmap_name = config.base.COLOR_MAP

        bar_width = 360.0 / len(bin_centers)
        colors = [color_mapper.get_color(angle, cmap_name) for angle in bin_centers]
        ax.bar(bin_centers, histogram, width=bar_width, color=colors, alpha=0.7,
               edgecolor='k', linewidth=0.5, label='Histogram')

        # Detected peaks
        peaks = analysis_result.peaks
        peak_centers = bin_centers[peaks]
        if len(peaks) > 0:
            ax.plot(peak_centers, histogram[peaks], 'ko', markersize=5,
                   label='Detected Peaks')

        # Gaussian fits with annotations
        if analysis_result.gaussian_fits:
            x_smooth = np.linspace(0, 360, 1000)
            for i, fit in enumerate(analysis_result.gaussian_fits):
                if 'kappa' in fit:
                    y_smooth = _vonmises_curve(x_smooth, fit['amplitude'], fit['mean'], fit['kappa'])
                else:
                    y_smooth = _gaussian(x_smooth, fit['amplitude'], fit['mean'], fit['std'])
                gauss_label = 'Fitted Gaussian Curves' if i == 0 else None
                ax.plot(x_smooth, y_smooth, color='red', linestyle='--', linewidth=2,
                       label=gauss_label)
                peak_y = fit['amplitude']
                if fit['mean'] > 100:
                    text_x = fit['mean'] - 40
                else:
                    text_x = fit['mean'] + 5
                ax.text(text_x, peak_y,
                       f'Mean: {fit["mean"]:.0f}°\nStd: {fit["std"]:.2f}',
                       verticalalignment='center', horizontalalignment='left', fontsize=9, linespacing=1.6)

        # Peak region highlights and ratio
        if len(peaks) >= 2:
            directivities = analysis_result.directivities
            center1 = bin_centers[peaks[0]]
            center2 = bin_centers[peaks[1]]
            count1 = DirectivityAnalyzer.count_samples_in_peak_region(directivities, center1, peak_half_width)
            count2 = DirectivityAnalyzer.count_samples_in_peak_region(directivities, center2, peak_half_width)

            ymax = ax.get_ylim()[1] * 1.15
            ax.set_ylim(0, ymax)

            # Peak 1 region (blue)
            p1_l = (center1 - peak_half_width) % 360
            p1_r = (center1 + peak_half_width) % 360
            if p1_l < p1_r:
                ax.fill_between([p1_l, p1_r], [0, 0], [ymax, ymax],
                               color='blue', alpha=0.2, label='Peak 1 Region')
            else:
                ax.fill_between([0, p1_r], [0, 0], [ymax, ymax],
                               color='blue', alpha=0.2)
                ax.fill_between([p1_l, 360], [0, 0], [ymax, ymax],
                               color='blue', alpha=0.2, label='Peak 1 Region')

            # Peak 2 region (red)
            p2_l = (center2 - peak_half_width) % 360
            p2_r = (center2 + peak_half_width) % 360
            if p2_l < p2_r:
                ax.fill_between([p2_l, p2_r], [0, 0], [ymax, ymax],
                               color='red', alpha=0.2, label='Peak 2 Region')
            else:
                ax.fill_between([0, p2_r], [0, 0], [ymax, ymax],
                               color='red', alpha=0.2)
                ax.fill_between([p2_l, 360], [0, 0], [ymax, ymax],
                               color='red', alpha=0.2, label='Peak 2 Region')

            ratio = count2 / count1 if count1 > 0 else None
            if ratio is not None:
                mid_x = (center1 + center2) / 2.0
                ax.text(mid_x, 0.95,
                       f'Peak 1 count: {count1}\nPeak 2 count: {count2}\nN2/N1 ratio: {ratio:.2f}',
                       transform=ax.get_xaxis_transform(),
                       verticalalignment='top', horizontalalignment='center',
                       fontsize=9, linespacing=1.6)

        ax.set_xlabel('Direction from the East (degree)', fontsize=12)
        ax.set_ylabel('Number of Earthquake Pairs', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlim(0, 360)
        ax.grid(True, alpha=0.3, color='gray', linestyle='--')
        ax.legend(loc='upper right')

        _add_direction_colorbar(ax, cmap_name)

        plt.tight_layout()
        if save_filename:
            self.save_figure(fig, save_filename)
        return fig

    def plot_directivity_ratio_evolution(self,
                                          temporal_result: TemporalDirectivityResult,
                                          show_confidence: bool = True,
                                          title: str = "Directivity Ratio Evolution",
                                          save_filename: Optional[str] = None) -> plt.Figure:
        """Plot N2/N1 ratio evolution (log y-scale).

        Sliding mode:  multiple window-size curves with per-curve CI shading.
        Cumulative mode: single curve showing ratio convergence from first event.
        """
        is_cumulative = getattr(temporal_result, 'mode', 'sliding') == 'cumulative'

        fig, ax = plt.subplots(figsize=(12, 8))

        if is_cumulative:
            color_palette = ['#1f77b4']  # single blue curve
        else:
            color_palette = ['blue', 'red', 'green', 'purple', 'orange']

        for idx, ws in enumerate(temporal_result.window_sizes):
            days = temporal_result.times_by_window[idx]
            ratios = temporal_result.ratios_by_window[idx]
            if len(days) == 0:
                continue
            color = color_palette[idx % len(color_palette)]

            if is_cumulative:
                label = 'Cumulative from first event'
                ax.plot(days, ratios, linestyle='-', color=color, linewidth=2,
                       label=label)
            else:
                ax.plot(days, ratios, linestyle='-', marker='.',
                       color=color, markersize=2, linewidth=2,
                       label=f'{ws:.1f} days')

            # Confidence interval shading (label only first time)
            if show_confidence:
                ci_lower = temporal_result.ci_lower_by_window[idx]
                ci_upper = temporal_result.ci_upper_by_window[idx]
                if len(ci_lower) == len(days) and len(days) > 0:
                    ci_label = '95% CI (H0: ratio=1)' if (idx == 0 or is_cumulative) else None
                    ax.fill_between(days, ci_lower, ci_upper,
                                   color='gray', alpha=0.15, label=ci_label)

        ax.set_yscale('log')
        ax.set_ylim([0.1, 10.0])
        ax.set_yticks([0.1, 0.2, 0.5, 1, 2, 5, 10])
        ax.set_yticklabels(['0.1', '0.2', '0.5', '1', '2', '5', '10'])
        ax.axhline(y=1, color='k', linestyle='--', alpha=0.3)

        if is_cumulative:
            ax.set_xlabel('Days since first event (cumulative window)', fontsize=12)
        else:
            ax.set_xlabel('Days since first event', fontsize=12)
        ax.set_ylabel('N2/N1 Ratio', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, which='both', ls='-', alpha=0.2)
        # Reorder: 95% CI at the bottom
        handles, labels = ax.get_legend_handles_labels()
        ci_idx = next((i for i, lbl in enumerate(labels) if 'CI' in lbl), None)
        if ci_idx is not None:
            handles.append(handles.pop(ci_idx))
            labels.append(labels.pop(ci_idx))
        ax.legend(handles, labels, loc='upper left', fontsize=9, framealpha=0.85)

        plt.tight_layout()
        if save_filename:
            self.save_figure(fig, save_filename)
        return fig

    def plot_single_window_ratio(self,
                                  temporal_result: TemporalDirectivityResult,
                                  window_index: Optional[int] = None,
                                  show_confidence: bool = True,
                                  title: str = "Directivity Ratio (Best Window)",
                                  save_filename: Optional[str] = None) -> plt.Figure:
        """Plot N2/N1 ratio for a single best window size.

        Selects the window with the most data points by default.
        """
        # Pick best window: most data points
        if window_index is None:
            n_points = [len(arr) for arr in temporal_result.times_by_window]
            if all(n == 0 for n in n_points):
                raise ValueError("No data in any window")
            window_index = int(np.argmax(n_points))

        ws = temporal_result.window_sizes[window_index]
        days = temporal_result.times_by_window[window_index]
        ratios = temporal_result.ratios_by_window[window_index]
        ci_lower = temporal_result.ci_lower_by_window[window_index]
        ci_upper = temporal_result.ci_upper_by_window[window_index]

        fig, ax = plt.subplots(figsize=(10, 6))

        if show_confidence and len(ci_lower) == len(days) and len(days) > 0:
            ax.fill_between(days, ci_lower, ci_upper,
                           color='gray', alpha=0.2,
                           label='95% CI (H0: ratio=1)')

        ax.plot(days, ratios, 'k-', linewidth=2, label=f'{ws:.1f} days window')
        ax.plot(days, ratios, 'k.', markersize=3, alpha=0.5)

        ax.axhline(y=1, color='k', linestyle='--', alpha=0.3, label='Ratio = 1')

        ax.set_xlabel('Days since first event', fontsize=12)
        ax.set_ylabel('N2/N1 Ratio', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, linestyle='--', alpha=0.4)
        ax.legend(loc='upper left', fontsize=10, framealpha=0.85)

        plt.tight_layout()
        if save_filename:
            self.save_figure(fig, save_filename)
        return fig

class SeismicityVisualizer(BaseVisualizer):
    """Seismic activity visualizer"""

    def plot_epicenter_map(self, events: List[EarthquakeEvent],
                          title: str = "Earthquake Epicenters",
                          show_magnitude: bool = True,
                          color_by_directivity: bool = True,
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
        cmap_name: str
        cbar_label: str

        directivity_assigned = False
        first_event_idx: Optional[int] = None
        if color_by_directivity and len(events) >= 2:
            events_with_time = [e for e in events if e.time is not None]
            if len(events_with_time) >= 2:
                sorted_events = sorted(events, key=lambda e: e.time)
                sorted_lats = np.array([e.latitude for e in sorted_events])
                sorted_lons = np.array([e.longitude for e in sorted_events])

                # Haversine directivity for consecutive pairs
                lat1 = np.radians(sorted_lats[:-1])
                lat2 = np.radians(sorted_lats[1:])
                lon1 = np.radians(sorted_lons[:-1])
                lon2 = np.radians(sorted_lons[1:])

                y = np.sin(lon2 - lon1) * np.cos(lat2)
                x = (np.cos(lat1) * np.sin(lat2) -
                     np.sin(lat1) * np.cos(lat2) * np.cos(lon2 - lon1))
                pair_directivities = np.degrees(np.arctan2(y, x))
                pair_directivities = (pair_directivities + 360) % 360

                # Assign directivity to each event: event i gets directivity i-1→i
                event_to_directivity: Dict[int, float] = {}
                for i, e in enumerate(sorted_events):
                    if i == 0:
                        event_to_directivity[id(e)] = pair_directivities[0]
                    else:
                        event_to_directivity[id(e)] = float(pair_directivities[i - 1])

                colors = [event_to_directivity[id(e)] for e in events]
                cmap_name = config.base.COLOR_MAP
                cbar_label = 'Directivity (°)'
                directivity_assigned = True

                # Find first event (earliest in time) in original list for star marker
                first_event = sorted_events[0]
                for idx, e in enumerate(events):
                    if id(e) == id(first_event):
                        first_event_idx = idx
                        break

        if not directivity_assigned:
            colors = mags
            cmap_name = 'Reds'
            cbar_label = 'Magnitude'

        sizes = [get_size(m) for m in mags]

        scatter_kwargs: Dict[str, Any] = dict(
            c=colors, s=sizes, cmap=cmap_name, alpha=0.7, edgecolors='k', linewidth=0.5
        )
        if directivity_assigned:
            scatter_kwargs['vmin'] = 0
            scatter_kwargs['vmax'] = 360

        scatter = ax.scatter(lons, lats, **scatter_kwargs)

        # Mark first event (earliest in time) with a red star
        if first_event_idx is not None:
            ax.scatter(lons[first_event_idx], lats[first_event_idx],
                      marker='*', color='red', s=get_size(mags[first_event_idx]) * 1.5,
                      zorder=5, label='First event')

        ax.set_xlabel('Longitude', fontsize=12)
        ax.set_ylabel('Latitude', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)

        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label(cbar_label, fontsize=12)
        if directivity_assigned:
            cbar.set_ticks(np.linspace(0, 360, num=5))
            cbar.set_ticklabels([f'{int(x)}°' for x in np.linspace(0, 360, num=5)])

        if show_magnitude:
            mag_handles = []
            mag_levels = sorted(list(set([min_mag, np.mean(mags), max_mag])))
            for mag in mag_levels:
                mag_handles.append(ax.scatter([], [], c='gray', s=get_size(mag),
                                   alpha=0.7, edgecolors='k'))

            legend_labels = [f'{mag:.1f}' for mag in mag_levels]
            if first_event_idx is not None:
                mag_handles.append(ax.scatter([], [], marker='*', color='red', s=100,
                                   edgecolors='k'))
                legend_labels.append('First event')

            ax.legend(mag_handles, legend_labels,
                     title='Magnitude', loc='best', fontsize=10, frameon=True)

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

        ax1.scatter(times, mags, c=mags, cmap='Reds', s=30, alpha=0.7, edgecolors='k', linewidth=0.5)
        ax1.set_ylabel('Magnitude', fontsize=12)
        ax1.set_title(title, fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)

        if ax2 is not None:
            ax2.hist(mags, bins=20, alpha=0.7, color='skyblue', edgecolor='k')
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

        ax1.hist(depths, bins=30, alpha=0.7, color='green', edgecolor='k')
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

    def plot_dtime_histogram(self, analysis_result: DirectivityAnalysisResult,
                             bins: int = 50, dtime_range: Optional[Tuple[float, float]] = None,
                             title: str = "Inter-event Time Distribution",
                             save_filename: Optional[str] = None,
                             ax: Optional[plt.Axes] = None) -> plt.Figure:
        """Plot histogram of inter-event times (seconds)."""
        if ax is None:
            fig, ax = plt.subplots(figsize=self.figsize)
        else:
            fig = ax.get_figure() # type: ignore

        dtimes = analysis_result.dtimes_seconds
        if len(dtimes) == 0:
            ax.set_title(title)
            return fig

        valid = dtimes[dtimes > 0]
        if dtime_range is None:
            dtime_range = (0, np.percentile(valid, 99))
        ax.hist(valid, bins=bins, range=dtime_range, edgecolor='k', alpha=0.7, color='gray')
        ax.set_xlabel('Dtime (seconds)', fontsize=12)
        ax.set_ylabel('Number of Earthquake Pairs', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)

        mean_v = np.mean(valid)
        median_v = np.median(valid)
        ax.text(0.98, 0.95, f'Mean: {mean_v:.1f} s\nMedian: {median_v:.1f} s',
                transform=ax.transAxes, verticalalignment='top',
                horizontalalignment='right',
                fontsize=10, linespacing=1.6)
        # Mark mean and median on histogram
        ax.axvline(mean_v, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label='Mean')
        ax.axvline(median_v, color='blue', linestyle='--', linewidth=1.5, alpha=0.7, label='Median')
        ax.legend(loc='upper center', fontsize=9)

        plt.tight_layout()
        if save_filename:
            self.save_figure(fig, save_filename)
        return fig

    def plot_speed_histogram(self, analysis_result: DirectivityAnalysisResult,
                             bins: int = 50, speed_range: Optional[Tuple[float, float]] = None,
                             title: str = "Migration Speed Distribution",
                             save_filename: Optional[str] = None,
                             ax: Optional[plt.Axes] = None) -> plt.Figure:
        """Plot histogram of migration speeds (km/s)."""
        if ax is None:
            fig, ax = plt.subplots(figsize=self.figsize)
        else:
            fig = ax.get_figure() # type: ignore

        speeds = analysis_result.speeds
        if len(speeds) == 0:
            ax.set_title(title)
            return fig

        valid = speeds[~np.isnan(speeds)]
        if speed_range is None:
            speed_range = (0, np.percentile(valid, 95))
        ax.hist(valid, bins=bins, range=speed_range, edgecolor='k', alpha=0.7, color='gray')
        ax.set_xlabel('Speed (km/s)', fontsize=12)
        ax.set_ylabel('Number of Earthquake Pairs', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)

        mean_v = np.mean(valid)
        median_v = np.median(valid)
        ax.text(0.98, 0.95, f'Mean: {mean_v:.5f} km/s\nMedian: {median_v:.5f} km/s',
                transform=ax.transAxes, verticalalignment='top',
                horizontalalignment='right',
                fontsize=10, linespacing=1.6)
        ax.axvline(mean_v, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label='Mean')
        ax.axvline(median_v, color='blue', linestyle='--', linewidth=1.5, alpha=0.7, label='Median')
        ax.legend(loc='upper center', fontsize=9)

        plt.tight_layout()
        if save_filename:
            self.save_figure(fig, save_filename)
        return fig

    def plot_dtime_evolution(self, analysis_result: DirectivityAnalysisResult,
                             title: str = "SEP Inter-event Time vs. Time",
                             save_filename: Optional[str] = None,
                             ax: Optional[plt.Axes] = None) -> plt.Figure:
        """Plot SEP dtime vs. pair occurrence time."""
        if ax is None:
            fig, ax = plt.subplots(figsize=self.figsize)
        else:
            fig = ax.get_figure() # type: ignore

        dtimes = analysis_result.dtimes_seconds
        pair_times = analysis_result.pair_times
        if len(dtimes) == 0 or len(pair_times) == 0:
            ax.set_title(title)
            return fig

        """  # noqa — module-level import above"""
        pair_dt = [datetime.fromtimestamp(t) for t in pair_times]
        valid = dtimes > 0
        ax.scatter([pair_dt[i] for i in range(len(pair_dt)) if valid[i]],
                  dtimes[valid], s=5, alpha=0.5, color='steelblue')
        ax.set_ylabel('Dtime (seconds)', fontsize=12)
        ax.set_xlabel('Pair Time', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()
        plt.tight_layout()
        if save_filename:
            self.save_figure(fig, save_filename)
        return fig

    def plot_speed_evolution(self, analysis_result: DirectivityAnalysisResult,
                             title: str = "SEP Speed vs. Time",
                             save_filename: Optional[str] = None,
                             ax: Optional[plt.Axes] = None) -> plt.Figure:
        """Plot SEP speed vs. pair occurrence time."""
        if ax is None:
            fig, ax = plt.subplots(figsize=self.figsize)
        else:
            fig = ax.get_figure() # type: ignore

        speeds = analysis_result.speeds
        pair_times = analysis_result.pair_times
        if len(speeds) == 0 or len(pair_times) == 0:
            ax.set_title(title)
            return fig

        """  # noqa — module-level import above"""
        pair_dt = [datetime.fromtimestamp(t) for t in pair_times]
        valid = ~np.isnan(speeds)
        ax.scatter([pair_dt[i] for i in range(len(pair_dt)) if valid[i]],
                  speeds[valid], s=5, alpha=0.5, color='darkred')
        ax.set_ylabel('Speed (km/s)', fontsize=12)
        ax.set_xlabel('Pair Time', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        fig.autofmt_xdate()
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

    def create_interactive_histogram(self, analysis_result: DirectivityAnalysisResult,
                                   title: str = "Interactive Directivity Histogram") -> "go.Figure":
        """Create interactive directivity histogram"""
        import plotly.graph_objects as go

        bin_centers = analysis_result.bin_centers
        histogram = analysis_result.histogram

        fig = go.Figure(data=[go.Bar(
            x=bin_centers,
            y=histogram,
            marker_color=[mcolors.to_hex(color_mapper.get_color(angle, config.base.COLOR_MAP)) for angle in bin_centers],
            hovertemplate='<b>Directivity: %{x:.1f}°</b><br>Frequency: %{y}<extra></extra>'
        )])

        if analysis_result.gaussian_fits:
            x_smooth = np.linspace(0, 360, 1000)

            for i, fit in enumerate(analysis_result.gaussian_fits):
                if 'kappa' in fit:
                    y_smooth = _vonmises_curve(x_smooth, fit['amplitude'], fit['mean'], fit['kappa'])
                else:
                    y_smooth = _gaussian(x_smooth, fit['amplitude'], fit['mean'], fit['std'])

                fig.add_trace(go.Scatter(
                    x=x_smooth,
                    y=y_smooth,
                    mode='lines',
                    name=f"Gaussian {i+1}: μ={fit['mean']:.1f}°, σ={fit['std']:.1f}°",
                    line=dict(color='red', width=2)
                ))

        fig.update_layout(
            title=title,
            xaxis_title="Directivity (degrees)",
            yaxis_title="Frequency",
            showlegend=bool(analysis_result.gaussian_fits)
        )
        return fig

class ComprehensiveVisualizer(BaseVisualizer):
    """Comprehensive analysis visualizer"""

    def __init__(self):
        """Initialize comprehensive analysis visualizer"""
        super().__init__()
        self.directivity_viz = DirectivityVisualizer()
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

        # 3. Directivity histogram
        ax3 = fig.add_subplot(gs[1, :])
        self.directivity_viz.plot_directivity_histogram(
            analysis_result.directional_analysis,
            title="Directivity Distribution with Gaussian Fits",
            ax=ax3
        )

        # 4. Polar plot
        ax4 = fig.add_subplot(gs[2, 0], projection='polar')
        self.directivity_viz.plot_polar_histogram(
            analysis_result.directional_analysis,
            title="Polar Directivity",
            ax=ax4
        )

        # 5. Depth distribution
        ax5 = fig.add_subplot(gs[2, 1])
        depths = [e.depth for e in events]
        if depths:
            ax5.hist(depths, bins=20, alpha=0.7, color='green', edgecolor='k')
        ax5.set_xlabel('Depth (km)')
        ax5.set_ylabel('Frequency')
        ax5.set_title('Depth Distribution')
        ax5.grid(True, alpha=0.3)

        # 6. Magnitude distribution
        ax6 = fig.add_subplot(gs[2, 2])
        mags = [e.magnitude for e in events]
        if mags:
            ax6.hist(mags, bins=20, alpha=0.7, color='orange', edgecolor='k')
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
                family='monospace', linespacing=1.6)

        fig.suptitle(title, fontsize=16, fontweight='bold', y=0.98)

        if save_filename:
            self.save_figure(fig, save_filename)

        return fig

# Convenience functions
def plot_directivity_histogram(analysis_result: DirectivityAnalysisResult, output_dir: str = "", **kwargs: Any) -> plt.Figure:
    """Plot directivity histogram (convenience function)"""
    viz = DirectivityVisualizer(output_dir=output_dir)
    return viz.plot_directivity_histogram(analysis_result, **kwargs)

def plot_polar_histogram(analysis_result: DirectivityAnalysisResult, output_dir: str = "", **kwargs: Any) -> plt.Figure:
    """Plot polar histogram (convenience function)"""
    viz = DirectivityVisualizer(output_dir=output_dir)
    return viz.plot_polar_histogram(analysis_result, **kwargs)

def plot_epicenter_map(events: List[EarthquakeEvent], output_dir: str = "", **kwargs: Any) -> plt.Figure:
    """Plot epicenter map (convenience function)"""
    viz = SeismicityVisualizer(output_dir=output_dir)
    return viz.plot_epicenter_map(events, **kwargs)

def plot_dtime_histogram(analysis_result: DirectivityAnalysisResult, output_dir: str = "", **kwargs: Any) -> plt.Figure:
    """Plot dtime histogram (convenience function)"""
    viz = SeismicityVisualizer(output_dir=output_dir)
    return viz.plot_dtime_histogram(analysis_result, **kwargs)

def plot_speed_histogram(analysis_result: DirectivityAnalysisResult, output_dir: str = "", **kwargs: Any) -> plt.Figure:
    """Plot speed histogram (convenience function)"""
    viz = SeismicityVisualizer(output_dir=output_dir)
    return viz.plot_speed_histogram(analysis_result, **kwargs)

def plot_dtime_evolution(analysis_result: DirectivityAnalysisResult, output_dir: str = "", **kwargs: Any) -> plt.Figure:
    """Plot dtime vs time (convenience function)"""
    viz = SeismicityVisualizer(output_dir=output_dir)
    return viz.plot_dtime_evolution(analysis_result, **kwargs)

def plot_speed_evolution(analysis_result: DirectivityAnalysisResult, output_dir: str = "", **kwargs: Any) -> plt.Figure:
    """Plot speed vs time (convenience function)"""
    viz = SeismicityVisualizer(output_dir=output_dir)
    return viz.plot_speed_evolution(analysis_result, **kwargs)

def create_analysis_dashboard(events: List[EarthquakeEvent], analysis_result: MigrationAnalysisResult, output_dir: str = "", **kwargs: Any) -> plt.Figure:
    """Create analysis dashboard (convenience function)"""
    viz = ComprehensiveVisualizer(output_dir=output_dir)
    return viz.create_analysis_dashboard(events, analysis_result, **kwargs)
