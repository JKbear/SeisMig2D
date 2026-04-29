"""
Seismic Analysis Core Module

This module contains the core analysis functions for seismicity migration analysis,
including bearing calculation, histogram generation, peak detection, and Gaussian fitting.
"""

import numpy as np
import pandas as pd
import logging
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from scipy.optimize import curve_fit
from scipy.stats import norm
import warnings

try:
    import peakutils
    PEAKUTILS_AVAILABLE = True
except ImportError:
    PEAKUTILS_AVAILABLE = False
    warnings.warn("peakutils library not available, using alternative peak detection algorithm")

from src.config import get_config
from src.catalog_reader import EarthquakeEvent
from src.utils import get_geometry_calculator, get_statistics_calculator

# Get global configuration and tools
config = get_config()
geometry_calc = get_geometry_calculator()
stats_calc = get_statistics_calculator()
logger = logging.getLogger(__name__)

@dataclass
class BearingAnalysisResult:
    """Bearing analysis result data class"""
    bearings: np.ndarray
    distances: np.ndarray
    weights: np.ndarray
    histogram: np.ndarray
    bin_edges: np.ndarray
    bin_centers: np.ndarray
    peaks: np.ndarray
    peak_properties: Dict[str, Any]
    gaussian_fits: List[Dict[str, Any]]
    statistics: Dict[str, Any]

@dataclass
class MigrationAnalysisResult:
    """Migration analysis result data class"""
    temporal_analysis: Dict[str, Any]
    spatial_analysis: Dict[str, Any]
    directional_analysis: BearingAnalysisResult
    magnitude_analysis: Dict[str, Any]
    summary_statistics: Dict[str, Any]

class BearingAnalyzer:
    """Bearing analyzer"""

    def __init__(self):
        """Initialize bearing analyzer"""
        self.bins: int = config.base.HIST_BINS
        self.range: Tuple[int, int] = config.base.HIST_RANGE
        self.peak_threshold: float = config.base.GAUSSIAN_PEAK_THRESHOLD
        self.min_distance: int = config.base.GAUSSIAN_MIN_DISTANCE

    def calculate_event_pairs(self, events: List[EarthquakeEvent],
                              min_distance_km: float = 0.1,
                              max_distance_km: float = 1000.0,
                              min_time_diff_hours: float = 0.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calculate azimuth, distance and weights for earthquake event pairs (vectorized)"""
        n_events = len(events)
        if n_events < 2:
            return np.array([]), np.array([]), np.array([])

        # Extract event data into arrays
        lats = np.array([e.latitude for e in events])
        lons = np.array([e.longitude for e in events])
        mags = np.array([e.magnitude for e in events])
        times = np.array([e.time for e in events])

        # Vectorized distance and bearing calculation using broadcasting
        lat1 = lats[:, np.newaxis]
        lon1 = lons[:, np.newaxis]
        lat2 = lats[np.newaxis, :]
        lon2 = lons[np.newaxis, :]

        # Haversine formula (vectorized)
        R = 6371.0  # Earth radius in km
        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        delta_lat = np.radians(lat2 - lat1)
        delta_lon = np.radians(lon2 - lon1)

        a = (np.sin(delta_lat / 2)**2 +
             np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(delta_lon / 2)**2)
        distances_matrix = R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        # Bearing formula (vectorized)
        y = np.sin(np.radians(lon2 - lon1)) * np.cos(lat2_rad)
        x = (np.cos(lat1_rad) * np.sin(lat2_rad) -
             np.sin(lat1_rad) * np.cos(lat2_rad) * np.cos(np.radians(lon2 - lon1)))
        bearings_matrix = np.degrees(np.arctan2(y, x))
        bearings_matrix = (bearings_matrix + 360) % 360

        # Upper triangle indices (i < j)
        i_idx, j_idx = np.triu_indices(n_events, k=1)

        bearings = bearings_matrix[i_idx, j_idx]
        distances = distances_matrix[i_idx, j_idx]
        mags_i = mags[i_idx]
        mags_j = mags[j_idx]

        # Filter by distance
        mask = (distances >= min_distance_km) & (distances <= max_distance_km)
        bearings = bearings[mask]
        distances = distances[mask]
        mags_i = mags_i[mask]
        mags_j = mags_j[mask]
        i_idx = i_idx[mask]
        j_idx = j_idx[mask]

        # Filter by time if needed
        if min_time_diff_hours > 0 and times[0] is not None:
            times_i = np.array([t.timestamp() if t else 0 for t in times[i_idx]])
            times_j = np.array([t.timestamp() if t else 0 for t in times[j_idx]])
            time_diffs = np.abs(times_j - times_i) / 3600
            mask = time_diffs >= min_time_diff_hours
            bearings = bearings[mask]
            distances = distances[mask]
            mags_i = mags_i[mask]
            mags_j = mags_j[mask]

        # Calculate weights
        mag_weight = (mags_i + mags_j) / 2.0
        distance_weight = 1.0 / (1.0 + distances / 100.0)
        weights = mag_weight * distance_weight

        return bearings, distances, weights

    def _calculate_weight(self, event1: EarthquakeEvent, event2: EarthquakeEvent,
                          distance: Optional[float] = None) -> float:
        """Calculate event pair weight"""
        mag_weight = (event1.magnitude + event2.magnitude) / 2.0

        if distance is None:
            distance = geometry_calc.calculate_distance(
                event1.latitude, event1.longitude,
                event2.latitude, event2.longitude
            )
        distance_weight = 1.0 / (1.0 + distance / 100.0)

        return mag_weight * distance_weight

    def create_histogram(self, bearings: np.ndarray,
                       weights: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Create bearing histogram"""
        histogram, bin_edges = np.histogram(
            bearings,
            bins=self.bins,
            range=self.range,
            weights=weights,
            density=False
        )

        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        return histogram, bin_edges, bin_centers

    def detect_peaks(self, histogram: np.ndarray, bin_centers: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Detect peaks in histogram"""
        if PEAKUTILS_AVAILABLE:
            peaks = peakutils.indexes(
                histogram,
                thres=self.peak_threshold,
                min_dist=self.min_distance
            )
            peak_properties = {
                'peak_heights': histogram[peaks],
                'peak_positions': bin_centers[peaks],
                'peak_widths': self._estimate_peak_widths(histogram, peaks)
            }
        else:
            peaks = self._detect_peaks_alternative(histogram)
            peak_properties = {
                'peak_heights': histogram[peaks],
                'peak_positions': bin_centers[peaks],
                'peak_widths': self._estimate_peak_widths(histogram, peaks)
            }

        return peaks, peak_properties

    def _detect_peaks_alternative(self, histogram: np.ndarray) -> np.ndarray:
        """Alternative peak detection algorithm"""
        peaks: List[int] = []
        max_hist = np.max(histogram)
        if max_hist == 0:
            return np.array([])

        threshold = self.peak_threshold * max_hist

        for i in range(1, len(histogram) - 1):
            if (histogram[i] > histogram[i-1] and
                histogram[i] > histogram[i+1] and
                histogram[i] > threshold):
                peaks.append(i)

        return np.array(peaks)

    def _estimate_peak_widths(self, histogram: np.ndarray, peaks: np.ndarray) -> np.ndarray:
        """Estimate peak widths"""
        widths: List[int] = []
        for peak in peaks:
            peak_height = histogram[peak]
            half_height = peak_height / 2.0

            left_idx = peak
            while left_idx > 0 and histogram[left_idx] > half_height:
                left_idx -= 1

            right_idx = peak
            while right_idx < len(histogram) - 1 and histogram[right_idx] > half_height:
                right_idx += 1

            widths.append(right_idx - left_idx)

        return np.array(widths)

    def fit_gaussians(self, histogram: np.ndarray, bin_centers: np.ndarray,
                     peaks: np.ndarray) -> List[Dict[str, Any]]:
        """Fit Gaussian distributions to peaks"""
        gaussian_fits: List[Dict[str, Any]] = []

        def gaussian(x: np.ndarray, amplitude: float, mean: float, std: float) -> np.ndarray:
            return amplitude * np.exp(-((x - mean) ** 2) / (2 * std ** 2))

        for i, peak in enumerate(peaks):
            try:
                window_size = 10
                start_idx = max(0, peak - window_size)
                end_idx = min(len(histogram), peak + window_size + 1)

                x_data = bin_centers[start_idx:end_idx]
                y_data = histogram[start_idx:end_idx]

                initial_amplitude = histogram[peak]
                initial_mean = bin_centers[peak]
                initial_std = 10.0

                initial_params = [initial_amplitude, initial_mean, initial_std]

                popt, pcov = curve_fit(gaussian, x_data, y_data, p0=initial_params)

                y_fit = gaussian(x_data, *popt)
                r_squared = self._calculate_r_squared(y_data, y_fit)

                fit_result: Dict[str, Any] = {
                    'amplitude': popt[0],
                    'mean': popt[1],
                    'std': abs(popt[2]),
                    'r_squared': r_squared,
                    'peak_index': int(peak),
                    'x_data': x_data,
                    'y_data': y_data,
                    'y_fit': y_fit
                }
                gaussian_fits.append(fit_result)

            except Exception as e:
                logger.warning(f"Gaussian fitting failed for peak {i} at {bin_centers[peak]:.1f}: {e}")
                continue

        return gaussian_fits

    def _calculate_r_squared(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate R² coefficient of determination"""
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)

        if ss_tot == 0:
            return 0.0

        r_squared = 1 - (ss_res / ss_tot)
        return max(0.0, r_squared)

    def analyze_bearings(self, events: List[EarthquakeEvent],
                        min_distance_km: float = 0.1,
                        max_distance_km: float = 1000.0) -> BearingAnalysisResult:
        """Execute complete bearing analysis"""
        bearings, distances, weights = self.calculate_event_pairs(
            events, min_distance_km, max_distance_km
        )

        if len(bearings) == 0:
            raise ValueError("Insufficient event pairs for analysis")

        histogram, bin_edges, bin_centers = self.create_histogram(bearings, weights)
        peaks, peak_properties = self.detect_peaks(histogram, bin_centers)
        gaussian_fits = self.fit_gaussians(histogram, bin_centers, peaks)

        # Calculate statistics
        stats_data = stats_calc.calculate_circular_statistics(bearings)
        statistics: Dict[str, Any] = {
            'total_pairs': len(bearings),
            'mean_distance': np.mean(distances),
            'std_distance': np.std(distances),
            'mean_weight': np.mean(weights),
            'n_peaks': len(peaks),
            'n_gaussian_fits': len(gaussian_fits),
            **stats_data
        }
        statistics['mean_bearing'] = np.mean(bearings)
        statistics['std_bearing'] = np.std(bearings)


        return BearingAnalysisResult(
            bearings=bearings,
            distances=distances,
            weights=weights,
            histogram=histogram,
            bin_edges=bin_edges,
            bin_centers=bin_centers,
            peaks=peaks,
            peak_properties=peak_properties,
            gaussian_fits=gaussian_fits,
            statistics=statistics
        )

class MigrationAnalyzer:
    """Seismic migration analyzer"""

    def __init__(self):
        """Initialize migration analyzer"""
        self.bearing_analyzer = BearingAnalyzer()

    def temporal_analysis(self, events: List[EarthquakeEvent],
                         time_window_days: int = 30) -> Dict[str, Any]:
        """Time series analysis.

        Note: This method calls bearing analysis for each sliding window,
        leading to O(n * k^2) complexity where n is the number of events
        and k is the typical window size. For catalogs with >500 events,
        consider reducing the time window or using bearing-only analysis.
        """
        if not events:
            return {}

        events_with_time = sorted([e for e in events if e.time], key=lambda x: x.time)

        if len(events_with_time) < 2:
            return {}

        MAX_WINDOW_EVENTS = 200
        times = [e.time for e in events_with_time]
        magnitudes = np.array([e.magnitude for e in events_with_time])

        time_diffs = np.array([(times[i] - times[i-1]).total_seconds() / 3600 for i in range(1, len(times))])

        mag_stats = stats_calc.calculate_statistics(magnitudes)
        time_stats = stats_calc.calculate_statistics(time_diffs)

        window_results: List[Dict[str, Any]] = []
        warned_large_window = False
        for i, current_event in enumerate(events_with_time):
            window_start_ts = current_event.time.timestamp() - time_window_days * 24 * 3600
            window_events = [
                event for event in events_with_time
                if window_start_ts <= event.time.timestamp() <= current_event.time.timestamp()
            ]

            if len(window_events) >= 2:
                if len(window_events) > MAX_WINDOW_EVENTS:
                    if not warned_large_window:
                        logger.warning(
                            f"Temporal analysis: window has {len(window_events)} events "
                            f"(> {MAX_WINDOW_EVENTS}). This may be slow. "
                            f"Consider reducing time_window_days from {time_window_days}."
                        )
                        warned_large_window = True
                    window_events = window_events[-MAX_WINDOW_EVENTS:]

                try:
                    bearing_result = self.bearing_analyzer.analyze_bearings(window_events)
                    window_results.append({
                        'time': current_event.time,
                        'event_count': len(window_events),
                        'mean_magnitude': np.mean([e.magnitude for e in window_events]),
                        'dominant_direction': bearing_result.gaussian_fits[0]['mean'] if bearing_result.gaussian_fits else None
                    })
                except ValueError:
                    continue

        total_duration = (times[-1] - times[0]).total_seconds() / (24 * 3600) if times else 0
        time_series_stats = {**time_stats, 'total_duration_days': total_duration}

        return {
            'time_series_stats': time_series_stats,
            'magnitude_stats': mag_stats,
            'window_analysis': window_results
        }

    def spatial_analysis(self, events: List[EarthquakeEvent]) -> Dict[str, Any]:
        """Spatial analysis"""
        if not events:
            return {}

        lats = np.array([e.latitude for e in events])
        lons = np.array([e.longitude for e in events])
        depths = np.array([e.depth for e in events])

        lat_stats = stats_calc.calculate_statistics(lats)
        lon_stats = stats_calc.calculate_statistics(lons)
        depth_stats = stats_calc.calculate_statistics(depths)

        lat_range = lat_stats.get('max', 0.0) - lat_stats.get('min', 0.0)
        lon_range = lon_stats.get('max', 0.0) - lon_stats.get('min', 0.0)

        # Use mean latitude for longitude degree conversion (1 deg lon ≈ 111km * cos(lat))
        mean_lat = np.mean(lats)
        km_per_lon_deg = 111.0 * np.cos(np.radians(mean_lat))
        km_per_lat_deg = 111.0
        area = lat_range * lon_range * km_per_lat_deg * km_per_lon_deg
        density = len(events) / area if area > 0 else 0

        return {
            'latitude_stats': lat_stats,
            'longitude_stats': lon_stats,
            'depth_stats': depth_stats,
            'spatial_range': {
                'latitude_range': lat_range,
                'longitude_range': lon_range
            },
            'spatial_density': density
        }

    def magnitude_analysis(self, events: List[EarthquakeEvent]) -> Dict[str, Any]:
        """Magnitude analysis"""
        if not events:
            return {}

        magnitudes = np.array([e.magnitude for e in events])
        mag_stats = stats_calc.calculate_statistics(magnitudes)

        min_mag, max_mag = mag_stats.get('min', 0.0), mag_stats.get('max', 5.0)
        magnitude_bins = np.arange(min_mag, max_mag + 0.1, 0.1)

        hist, bin_edges = np.histogram(magnitudes, bins=magnitude_bins)
        cumulative_freq = np.cumsum(hist[::-1])[::-1]

        b_value = self._estimate_b_value(magnitudes)

        return {
            'magnitude_stats': mag_stats,
            'magnitude_frequency': {
                'bins': bin_edges[:-1].tolist(),
                'frequency': hist.tolist(),
                'cumulative_frequency': cumulative_freq.tolist()
            },
            'b_value_estimate': b_value
        }

    def _estimate_b_value(self, magnitudes: np.ndarray, mc: Optional[float] = None) -> float:
        """Estimate b-value using the Aki-Utsu maximum likelihood method.

        Uses b = log10(e) / (mean(M) - Mc), where Mc is the completeness magnitude.
        If Mc is not provided, the 5th percentile of magnitudes is used as a simple
        completeness threshold estimate. For rigorous analysis, Mc should be
        determined independently (e.g., by the maximum curvature method).

        References:
            Aki, K. (1965). Maximum likelihood estimate of b in the formula
            log N = a - bM and its confidence limits. Bull. Earthquake Res.
            Inst., Univ. Tokyo, 43, 237-239.
        """
        if len(magnitudes) < 10:
            return 0.0

        if mc is None:
            # Use 5th percentile as a rough Mc estimate (better than min)
            mc = float(np.percentile(magnitudes, 5))

        above_mc = magnitudes[magnitudes >= mc]
        if len(above_mc) < 5:
            return 0.0

        mean_mag = np.mean(above_mc)
        # Apply correction for binned magnitudes: delta = M_bin_width / 2
        # Assume 0.1 magnitude unit binning unless otherwise known
        delta_mag = mean_mag - (mc - 0.05)
        b_value = np.log10(np.e) / delta_mag if delta_mag > 0 else 0.0

        return float(b_value)

    def comprehensive_analysis(self, events: List[EarthquakeEvent],
                               min_distance_km: float = 0.1,
                               max_distance_km: float = 1000.0,
                               time_window_days: int = 30) -> MigrationAnalysisResult:
        """Execute comprehensive analysis"""
        if len(events) < 2:
            raise ValueError("At least 2 earthquake events are required for analysis")

        directional_analysis = self.bearing_analyzer.analyze_bearings(
            events, min_distance_km, max_distance_km
        )

        temporal_analysis = self.temporal_analysis(events, time_window_days)
        spatial_analysis = self.spatial_analysis(events)
        magnitude_analysis = self.magnitude_analysis(events)

        summary_statistics: Dict[str, Any] = {
            'total_events': len(events),
            'analysis_parameters': {
                'min_distance_km': min_distance_km,
                'max_distance_km': max_distance_km,
                'time_window_days': time_window_days
            },
            'dominant_directions': [
                {
                    'mean': fit['mean'],
                    'std': fit['std'],
                    'amplitude': fit['amplitude']
                }
                for fit in directional_analysis.gaussian_fits[:3]
            ]
        }

        return MigrationAnalysisResult(
            temporal_analysis=temporal_analysis,
            spatial_analysis=spatial_analysis,
            directional_analysis=directional_analysis,
            magnitude_analysis=magnitude_analysis,
            summary_statistics=summary_statistics
        )

# Convenience functions
def analyze_seismicity_migration(events: List[EarthquakeEvent],
                               min_distance_km: float = 0.1,
                               max_distance_km: float = 1000.0,
                               time_window_days: int = 30) -> MigrationAnalysisResult:
    """Analyze seismic migration (convenience function)"""
    analyzer = MigrationAnalyzer()
    return analyzer.comprehensive_analysis(events, min_distance_km, max_distance_km, time_window_days)

def calculate_bearings(events: List[EarthquakeEvent],
                      min_distance_km: float = 0.1,
                      max_distance_km: float = 1000.0) -> BearingAnalysisResult:
    """Calculate bearings (convenience function)"""
    analyzer = BearingAnalyzer()
    return analyzer.analyze_bearings(events, min_distance_km, max_distance_km)
