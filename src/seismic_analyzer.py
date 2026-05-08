"""
Seismic Analysis Core Module

This module contains the core analysis functions for seismicity migration analysis,
including directivity calculation, histogram generation, peak detection, and Gaussian fitting.
"""

import numpy as np
import logging
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from scipy.optimize import minimize
from scipy.special import ive  # modified Bessel function I₀
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
class DirectivityAnalysisResult:
    """Directivity analysis result data class"""
    directivities: np.ndarray
    distances: np.ndarray
    weights: np.ndarray
    dtimes_seconds: np.ndarray = field(default_factory=lambda: np.array([]))
    speeds: np.ndarray = field(default_factory=lambda: np.array([]))
    pair_times: np.ndarray = field(default_factory=lambda: np.array([]))
    histogram: np.ndarray = field(default_factory=lambda: np.array([]))
    bin_edges: np.ndarray = field(default_factory=lambda: np.array([]))
    bin_centers: np.ndarray = field(default_factory=lambda: np.array([]))
    peaks: np.ndarray = field(default_factory=lambda: np.array([]))
    peak_properties: Dict[str, Any] = field(default_factory=dict)
    gaussian_fits: List[Dict[str, Any]] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MigrationAnalysisResult:
    """Migration analysis result data class"""
    temporal_analysis: Dict[str, Any]
    spatial_analysis: Dict[str, Any]
    directional_analysis: DirectivityAnalysisResult
    magnitude_analysis: Dict[str, Any]
    summary_statistics: Dict[str, Any]

@dataclass
class TemporalDirectivityResult:
    """Temporal directivity N2/N1 ratio evolution analysis result."""
    window_sizes: List[float]
    times_by_window: List[np.ndarray]       # days since catalog start, per window size
    ratios_by_window: List[np.ndarray]      # N2/N1 ratio per window
    n_totals_by_window: List[np.ndarray]    # total pairs per window
    ci_lower_by_window: List[np.ndarray]    # 95% CI lower bound per window
    ci_upper_by_window: List[np.ndarray]    # 95% CI upper bound per window
    statistics: Dict[str, Any]

class DirectivityAnalyzer:
    """Directivity analyzer"""

    def __init__(self):
        """Initialize directivity analyzer"""
        self.bins: int = config.base.HIST_BINS
        self.range: Tuple[int, int] = config.base.HIST_RANGE
        self.peak_threshold: float = config.base.GAUSSIAN_PEAK_THRESHOLD
        self.min_distance: int = config.base.GAUSSIAN_MIN_DISTANCE

    def calculate_event_pairs(self, events: List[EarthquakeEvent],
                              min_distance_km: float = 0.1,
                              max_distance_km: float = 1000.0,
                              min_time_diff_hours: float = 0.0,
                              min_dtime_seconds: float = 0.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Calculate azimuth, distance, weights, dtimes, and speeds for
        consecutive event pairs in time order. O(N) memory.
        """
        n_events = len(events)
        if n_events < 2:
            return (np.array([]), np.array([]), np.array([]),
                    np.array([]), np.array([]), np.array([]))

        # Sort events by time to ensure consecutive pairs are temporally adjacent
        events_sorted = sorted(events, key=lambda e: e.time if e.time else datetime.min)

        # Extract event data into arrays
        lats = np.array([e.latitude for e in events_sorted])
        lons = np.array([e.longitude for e in events_sorted])
        mags = np.array([e.magnitude for e in events_sorted])
        times = np.array([e.time.timestamp() if e.time else 0.0 for e in events_sorted])

        # Consecutive pairs: shift arrays by 1 (O(N) memory, O(N) time)
        lat1 = lats[:-1]
        lon1 = lons[:-1]
        lat2 = lats[1:]
        lon2 = lons[1:]
        mags_i = mags[:-1]
        mags_j = mags[1:]
        times_i = times[:-1]
        times_j = times[1:]

        # Time gaps (seconds)
        dtimes_seconds = times_j - times_i

        # Haversine distance (vectorized on 1D arrays)
        R = 6371.0
        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        delta_lat = np.radians(lat2 - lat1)
        delta_lon = np.radians(lon2 - lon1)

        a = (np.sin(delta_lat / 2)**2 +
             np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(delta_lon / 2)**2)
        distances = R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        # Directivity formula (vectorized on 1D arrays)
        y = np.sin(np.radians(lon2 - lon1)) * np.cos(lat2_rad)
        x = (np.cos(lat1_rad) * np.sin(lat2_rad) -
             np.sin(lat1_rad) * np.cos(lat2_rad) * np.cos(np.radians(lon2 - lon1)))
        directivities = np.degrees(np.arctan2(y, x))
        directivities = (directivities + 360) % 360

        # Combine all filters into a single mask
        mask = (distances >= min_distance_km) & (distances <= max_distance_km)
        if min_time_diff_hours > 0:
            mask &= (dtimes_seconds / 3600.0) >= min_time_diff_hours
        if min_dtime_seconds > 0:
            mask &= dtimes_seconds >= min_dtime_seconds

        # Apply mask once to all arrays
        directivities = directivities[mask]
        distances = distances[mask]
        mags_i = mags_i[mask]
        mags_j = mags_j[mask]
        dtimes_seconds = dtimes_seconds[mask]
        times_j = times_j[mask]

        # Calculate weights
        mag_weight = (mags_i + mags_j) / 2.0
        distance_weight = 1.0 / (1.0 + distances / 100.0)
        weights = mag_weight * distance_weight

        # Speeds (km/s), nan for zero/negative dt
        speeds = np.full_like(distances, np.nan)
        valid = dtimes_seconds > 0
        speeds[valid] = distances[valid] / dtimes_seconds[valid]

        return directivities, distances, weights, dtimes_seconds, speeds, times_j

    def create_histogram(self, directivities: np.ndarray,
                       weights: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Create directivity histogram"""
        histogram, bin_edges = np.histogram(
            directivities,
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

    def fit_vonmises_mixture(self, histogram: np.ndarray, bin_centers: np.ndarray,
                             peaks: np.ndarray) -> List[Dict[str, Any]]:
        """Fit a von Mises Mixture Model (vMMM) to the directivity histogram.

        Fits K components simultaneously to the full histogram, where K is the
        number of detected peaks. Uses L-BFGS-B optimisation with bounds.
        """
        K = len(peaks)
        if K == 0:
            return []

        # Convert bin centres to radians for fitting
        theta_rad = np.radians(bin_centers)
        y = histogram.astype(np.float64)
        y_sum = y.sum()
        if y_sum == 0:
            return []
        y_norm = y / y_sum  # normalise to PDF scale

        # --- von Mises PDF ---
        def vm_pdf(theta, mu_deg, kappa):
            """Von Mises PDF. theta and mu_deg in degrees, kappa >= 0."""
            # ive(0, kappa) = I₀(kappa) * exp(-kappa), avoids overflow
            return np.exp(kappa * (np.cos(np.radians(theta - mu_deg)) - 1.0)) / (
                2.0 * np.pi * ive(0, kappa))

        # --- Loss function ---
        def neg_log_likelihood(params):
            """Negative log-likelihood of von Mises mixture."""
            mus = params[:K]
            kappas = params[K:2*K]
            # weights: first K-1 free, last one constrained
            w_free = params[2*K:3*K-1]
            w = np.zeros(K)
            w[:K-1] = w_free
            w[-1] = 1.0 - w_free.sum()
            if w[-1] <= 0:
                return 1e12

            pdf = np.zeros_like(y_norm)
            for k in range(K):
                pdf += w[k] * vm_pdf(bin_centers, mus[k], kappas[k])
            pdf = np.maximum(pdf, 1e-300)
            return -np.sum(y_norm * np.log(pdf))

        # --- Initial guesses ---
        peak_heights = y[peaks].astype(np.float64)
        total_height = peak_heights.sum()
        init_weights = peak_heights / total_height  # normalise to sum to 1

        init_mus = np.array([bin_centers[p] for p in peaks], dtype=np.float64)
        init_kappas = np.full(K, 10.0)  # moderate concentration

        # Parameter vector: [mus (K), kappas (K), weights (K-1)]
        init_params = np.concatenate([init_mus, init_kappas, init_weights[:-1]])

        # Bounds: mu ∈ [0, 360], kappa ∈ [0.1, 200], w ∈ [0.01, 0.99]
        bounds = ([(0.0, 360.0)] * K +
                  [(0.1, 200.0)] * K +
                  [(0.01, 0.99)] * (K - 1))

        try:
            result = minimize(neg_log_likelihood, init_params, method='L-BFGS-B',
                            bounds=bounds, options={'maxiter': 500, 'disp': False})
            if not result.success:
                logger.warning(f"vMMM optimisation did not converge: {result.message}")
                return []

            mus_opt = result.x[:K]
            kappas_opt = result.x[K:2*K]
            w_free_opt = result.x[2*K:3*K-1]
            w_opt = np.zeros(K)
            w_opt[:K-1] = w_free_opt
            w_opt[-1] = 1.0 - w_free_opt.sum()

            # Build fit results (keep compatible structure)
            vm_fits: List[Dict[str, Any]] = []
            # Sort by weight descending
            order = np.argsort(-w_opt)
            for rank, idx in enumerate(order):
                # Compute σ-equivalent for compatibility: σ ≈ 1/√κ (degrees)
                if kappas_opt[idx] > 0.01:
                    sigma_equiv = np.degrees(1.0 / np.sqrt(kappas_opt[idx]))
                else:
                    sigma_equiv = 90.0

                # Peak bin height: take histogram value at bin nearest the fitted mean
                closest_bin = int(np.argmin(np.abs(bin_centers - mus_opt[idx])))
                peak_amplitude = float(y[closest_bin])

                # R² on the full histogram for this component
                y_pred = w_opt[idx] * vm_pdf(bin_centers, mus_opt[idx], kappas_opt[idx]) * y_sum
                r_squared = self._calculate_r_squared(y.astype(np.float64), y_pred)

                # Full mixture prediction for this component
                mixture_y = np.zeros_like(y_norm)
                for k in range(K):
                    mixture_y += w_opt[k] * vm_pdf(bin_centers, mus_opt[k], kappas_opt[k])
                mixture_y_full = mixture_y * y_sum

                vm_fits.append({
                    'amplitude': peak_amplitude,
                    'weight': float(w_opt[idx]),
                    'mean': float(mus_opt[idx]),
                    'std': float(sigma_equiv),
                    'kappa': float(kappas_opt[idx]),
                    'r_squared': float(r_squared),
                    'peak_index': int(peaks[idx]),
                    'x_data': bin_centers,
                    'y_data': y,
                    'y_fit': mixture_y_full,
                    'model': 'von_mises_mixture',
                })

            return vm_fits

        except Exception as e:
            logger.warning(f"von Mises mixture fitting failed: {e}")
            return []

    def _calculate_r_squared(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate R² coefficient of determination"""
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)

        if ss_tot == 0:
            return 0.0

        r_squared = 1 - (ss_res / ss_tot)
        return max(0.0, r_squared)

    def analyze_directivities(self, events: List[EarthquakeEvent],
                        min_distance_km: float = 0.1,
                        max_distance_km: float = 1000.0,
                        min_dtime_seconds: Optional[float] = None) -> DirectivityAnalysisResult:
        """Execute complete directivity analysis"""
        if min_dtime_seconds is None:
            min_dtime_seconds = config.base.MIN_DTIME_SECONDS
        directivities, distances, weights, dtimes_seconds, speeds, pair_times = self.calculate_event_pairs(
            events, min_distance_km, max_distance_km,
            min_dtime_seconds=min_dtime_seconds
        )

        if len(directivities) == 0:
            raise ValueError("Insufficient event pairs for analysis")

        histogram, bin_edges, bin_centers = self.create_histogram(directivities, weights)
        peaks, peak_properties = self.detect_peaks(histogram, bin_centers)
        gaussian_fits = self.fit_vonmises_mixture(histogram, bin_centers, peaks)

        # Calculate statistics
        stats_data = stats_calc.calculate_circular_statistics(directivities)
        statistics: Dict[str, Any] = {
            'total_pairs': len(directivities),
            'mean_distance': np.mean(distances),
            'std_distance': np.std(distances),
            'mean_dtime_seconds': float(np.mean(dtimes_seconds)) if len(dtimes_seconds) > 0 else 0.0,
            'mean_speed_kms': float(np.mean(speeds[~np.isnan(speeds)])) if np.any(~np.isnan(speeds)) else float('nan'),
            'mean_weight': np.mean(weights),
            'n_peaks': len(peaks),
            'n_gaussian_fits': len(gaussian_fits),
            **stats_data
        }
        statistics['mean_directivity'] = np.mean(directivities)
        statistics['std_directivity'] = np.std(directivities)


        return DirectivityAnalysisResult(
            directivities=directivities,
            distances=distances,
            weights=weights,
            dtimes_seconds=dtimes_seconds,
            speeds=speeds,
            pair_times=pair_times,
            histogram=histogram,
            bin_edges=bin_edges,
            bin_centers=bin_centers,
            peaks=peaks,
            peak_properties=peak_properties,
            gaussian_fits=gaussian_fits,
            statistics=statistics
        )

    @staticmethod
    def count_samples_in_peak_region(directivities: np.ndarray, peak_center: float,
                                      half_width: float) -> int:
        """Count samples within a half-width window around a peak center.

        Handles 0/360 degree boundary crossing.
        """
        directivities = directivities % 360
        lower = (peak_center - half_width) % 360
        upper = (peak_center + half_width) % 360
        if lower < upper:
            return int(np.sum((directivities >= lower) & (directivities <= upper)))
        else:
            return int(np.sum((directivities >= lower) | (directivities <= upper)))

    @staticmethod
    def calculate_confidence_intervals(N_total: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate 95% CI boundaries for N2/N1=1 under the null hypothesis.

        SE = 0.5 / sqrt(N), p = 0.5 ± 1.96·SE, ratio = p/(1-p).
        """
        with np.errstate(divide='ignore', invalid='ignore'):
            se = 0.5 / np.sqrt(N_total)
            p_upper = 0.5 + 1.96 * se
            p_lower = 0.5 - 1.96 * se
            upper_bound = p_upper / (1.0 - p_upper)
            lower_bound = p_lower / (1.0 - p_lower)
        return lower_bound, upper_bound

class MigrationAnalyzer:
    """Seismic migration analyzer"""

    def __init__(self):
        """Initialize migration analyzer"""
        self.directivity_analyzer = DirectivityAnalyzer()

    def temporal_analysis(self, events: List[EarthquakeEvent],
                         time_window_days: int = 30) -> Dict[str, Any]:
        """Time series analysis.

        Note: This method calls directivity analysis for each sliding window,
        leading to O(n * k^2) complexity where n is the number of events
        and k is the typical window size. For catalogs with >500 events,
        consider reducing the time window or using directivity-only analysis.
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
                    directivity_result = self.directivity_analyzer.analyze_directivities(window_events)
                    window_results.append({
                        'time': current_event.time,
                        'event_count': len(window_events),
                        'mean_magnitude': np.mean([e.magnitude for e in window_events]),
                        'dominant_direction': directivity_result.gaussian_fits[0]['mean'] if directivity_result.gaussian_fits else None
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

        directional_analysis = self.directivity_analyzer.analyze_directivities(
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

    def temporal_directivity_ratio_analysis(
        self, events: List[EarthquakeEvent],
        window_sizes: Optional[List[float]] = None,
        time_step: Optional[float] = None,
        peak_half_width: Optional[float] = None,
        min_events: Optional[int] = None
    ) -> TemporalDirectivityResult:
        """Sliding-window N2/N1 ratio analysis over time.

        Slides windows of various sizes across the catalog, computes
        the ratio of samples in the second dominant peak region to the
        first, and calculates 95% confidence intervals.
        """
        if window_sizes is None:
            window_sizes = config.base.SLIDING_WINDOW_SIZES
        if time_step is None:
            time_step = config.base.SLIDING_TIME_STEP
        if peak_half_width is None:
            peak_half_width = float(config.base.PEAK_HALF_WIDTH)
        if min_events is None:
            min_events = config.base.MIN_EVENTS_FOR_RATIO

        # Sort events by time
        events_with_time = [e for e in events if e.time is not None]
        if len(events_with_time) < min_events:
            raise ValueError(
                f"At least {min_events} events with time required, got {len(events_with_time)}"
            )
        events_sorted = sorted(events_with_time, key=lambda e: e.time)
        n_events = len(events_sorted)

        # Calculate all directivities once (O(N)) — no distance filter to keep
        # pair_times aligned
        all_directivities, _, _, _, _, _ = self.directivity_analyzer.calculate_event_pairs(
            events_sorted, min_distance_km=0.0, max_distance_km=1e9
        )
        if len(all_directivities) == 0:
            raise ValueError("No valid event pairs for ratio analysis")

        # Pair timestamps: pair i corresponds to events_sorted[i] -> events_sorted[i+1]
        pair_times = np.array([
            events_sorted[i + 1].time.timestamp() if events_sorted[i + 1].time else 0.0
            for i in range(n_events - 1)
        ])

        start_ts = events_sorted[0].time.timestamp()
        end_ts = events_sorted[-1].time.timestamp()
        step_sec = time_step * 86400.0

        times_by_window: List[np.ndarray] = []
        ratios_by_window: List[np.ndarray] = []
        n_totals_by_window: List[np.ndarray] = []
        ci_lower_by_window: List[np.ndarray] = []
        ci_upper_by_window: List[np.ndarray] = []
        total_windows = 0

        for ws in window_sizes:
            window_sec = ws * 86400.0
            times_list: List[float] = []
            ratios_list: List[float] = []
            n_totals_list: List[float] = []

            current = start_ts
            while current <= end_ts - window_sec:
                window_end = current + window_sec
                # O(log P) binary search instead of O(P) boolean mask
                left = np.searchsorted(pair_times, current, side='left')
                right = np.searchsorted(pair_times, window_end, side='right')
                N = right - left

                if N >= min_events:
                    subset = all_directivities[left:right]
                    hist, bin_edges, bin_centers = self.directivity_analyzer.create_histogram(subset)
                    peaks, _ = self.directivity_analyzer.detect_peaks(hist, bin_centers)

                    if len(peaks) >= 2:
                        center1 = bin_centers[peaks[0]]
                        center2 = bin_centers[peaks[1]]
                        count1 = DirectivityAnalyzer.count_samples_in_peak_region(
                            subset, center1, peak_half_width
                        )
                        count2 = DirectivityAnalyzer.count_samples_in_peak_region(
                            subset, center2, peak_half_width
                        )
                        if count1 > 0:
                            ratio = count2 / count1
                            midpoint_ts = current + window_sec / 2.0
                            days = (midpoint_ts - start_ts) / 86400.0
                            times_list.append(days)
                            ratios_list.append(ratio)
                            n_totals_list.append(float(N))
                            total_windows += 1

                current += step_sec

            times_by_window.append(np.array(times_list))
            ratios_by_window.append(np.array(ratios_list))
            n_totals_by_window.append(np.array(n_totals_list))
            ci_lower, ci_upper = DirectivityAnalyzer.calculate_confidence_intervals(
                np.array(n_totals_list)
            )
            ci_lower_by_window.append(ci_lower)
            ci_upper_by_window.append(ci_upper)

        statistics: Dict[str, Any] = {
            'catalog_duration_days': (end_ts - start_ts) / 86400.0,
            'total_pairs': len(all_directivities),
            'total_windows_computed': total_windows,
            'window_sizes_used': window_sizes,
            'mean_ratio_by_window': [
                float(np.mean(r)) if len(r) > 0 else float('nan')
                for r in ratios_by_window
            ],
        }

        return TemporalDirectivityResult(
            window_sizes=window_sizes,
            times_by_window=times_by_window,
            ratios_by_window=ratios_by_window,
            n_totals_by_window=n_totals_by_window,
            ci_lower_by_window=ci_lower_by_window,
            ci_upper_by_window=ci_upper_by_window,
            statistics=statistics,
        )

# Convenience functions
def analyze_seismicity_migration(events: List[EarthquakeEvent],
                               min_distance_km: float = 0.1,
                               max_distance_km: float = 1000.0,
                               time_window_days: int = 30) -> MigrationAnalysisResult:
    """Analyze seismic migration (convenience function)"""
    analyzer = MigrationAnalyzer()
    return analyzer.comprehensive_analysis(events, min_distance_km, max_distance_km, time_window_days)

def calculate_directivities(events: List[EarthquakeEvent],
                      min_distance_km: float = 0.1,
                      max_distance_km: float = 1000.0,
                      min_dtime_seconds: Optional[float] = None) -> DirectivityAnalysisResult:
    """Calculate directivities (convenience function)"""
    analyzer = DirectivityAnalyzer()
    return analyzer.analyze_directivities(events, min_distance_km, max_distance_km,
                                          min_dtime_seconds=min_dtime_seconds)
