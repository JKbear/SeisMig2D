"""
Seismicity Migration Analysis Utilities Module

This module contains utility functions for coordinate conversion,
bearing calculation, color mapping, and other common operations.
"""

import numpy as np
import math
from typing import Tuple, Optional, Union, List, Dict, Any
from pyproj import Transformer
from src.config import get_config, Config

# Get global configuration
config: Config = get_config()

class CoordinateConverter:
    """Coordinate conversion utility class"""

    def __init__(self):
        """Initialize coordinate converter"""
        self.transformer = Transformer.from_proj(
            config.base.WGS84_PROJ_STRING,
            config.base.WEB_MERCATOR_PROJ_STRING,
            always_xy=True
        )

    def wgs84_to_web_mercator(self, lon: float, lat: float) -> Tuple[float, float]:
        """Convert WGS84 to Web Mercator."""
        try:
            x, y = self.transformer.transform(lon, lat)
            return x, y
        except Exception as e:
            raise ValueError(f"Coordinate conversion failed: {e}")

    def batch_convert(self, lons: np.ndarray, lats: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Batch convert coordinates."""
        try:
            xs, ys = self.transformer.transform(lons, lats)
            return xs, ys
        except Exception as e:
            raise ValueError(f"Batch coordinate conversion failed: {e}")

class GeometryCalculator:
    """Geometry calculation utility class"""

    @staticmethod
    def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate bearing angle between two points (0-360 degrees)."""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)

        y = math.sin(delta_lon) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))

        bearing = math.degrees(math.atan2(y, x))
        bearing = (bearing + 360) % 360
        return bearing

    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula (km)."""
        R = 6371.0  # Earth radius in kilometers

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2)**2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c
        return distance

    @staticmethod
    def calculate_distance_and_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, float]:
        """Calculate both distance and bearing simultaneously."""
        distance = GeometryCalculator.calculate_distance(lat1, lon1, lat2, lon2)
        bearing = GeometryCalculator.calculate_bearing(lat1, lon1, lat2, lon2)
        return distance, bearing

# matplotlib imported once at module level for ColorMapper
_MATPLOTLIB_IMPORTED = False
_MATPLOTLIB_IMPORT_ERR: Optional[str] = None
try:
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    _MATPLOTLIB_IMPORTED = True
except ImportError as e:
    _MATPLOTLIB_IMPORT_ERR = str(e)
    plt = None  # type: ignore
    mcolors = None  # type: ignore

class ColorMapper:
    """Color mapping utility class"""

    @staticmethod
    def get_color(angle: float, colormap: str = "viridis") -> str:
        """Get color based on angle."""
        if _MATPLOTLIB_IMPORTED:
            normalized_angle = angle / 360.0
            cmap = plt.get_cmap(colormap)
            color = cmap(normalized_angle)
            return mcolors.to_hex(color)
        else:
            colors = [
                "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
                "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
            ]
            return colors[int(angle / 36) % len(colors)]

    @staticmethod
    def get_colormap_colors(n_colors: int, colormap: str = "viridis") -> List[str]:
        """Get multiple colors from color map."""
        if _MATPLOTLIB_IMPORTED:
            cmap = plt.get_cmap(colormap)
            return [mcolors.to_hex(cmap(i / (n_colors - 1))) for i in range(n_colors)]
        else:
            base_colors = [
                "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
                "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
            ]
            return [base_colors[i % len(base_colors)] for i in range(n_colors)]

class DataValidator:
    """Data validation utility class"""

    @staticmethod
    def validate_coordinates(lat: float, lon: float) -> bool:
        """Validate coordinate validity."""
        return -90 <= lat <= 90 and -180 <= lon <= 180

    @staticmethod
    def validate_magnitude(mag: float) -> bool:
        """Validate magnitude validity."""
        return -10 <= mag <= 10

    @staticmethod
    def validate_depth(depth: float) -> bool:
        """Validate depth validity."""
        return -100 <= depth <= 1000

    @staticmethod
    def validate_time_string(time_str: str, time_formats: Optional[List[str]] = None) -> bool:
        """Validate time string format."""
        if time_formats is None:
            time_formats = config.catalog.TIME_FORMATS

        from datetime import datetime
        for fmt in time_formats:
            try:
                datetime.strptime(time_str, fmt)
                return True
            except (ValueError, TypeError):
                continue
        return False

class StatisticsCalculator:
    """Statistical calculation utility class"""

    @staticmethod
    def calculate_statistics(data: np.ndarray) -> Dict[str, Any]:
        """Calculate basic statistical information."""
        if data.size == 0:
            return {
                "count": 0, "mean": 0.0, "std": 0.0, "min": 0.0,
                "max": 0.0, "median": 0.0, "q25": 0.0, "q75": 0.0
            }

        return {
            "count": int(len(data)),
            "mean": float(np.mean(data)),
            "std": float(np.std(data)),
            "min": float(np.min(data)),
            "max": float(np.max(data)),
            "median": float(np.median(data)),
            "q25": float(np.percentile(data, 25)),
            "q75": float(np.percentile(data, 75))
        }

    @staticmethod
    def calculate_circular_statistics(angles: np.ndarray) -> Dict[str, float]:
        """Calculate circular statistics (for angle data)."""
        if angles.size == 0:
            return {"circular_mean": 0.0, "circular_std": 0.0, "resultant_length": 0.0}

        angles_rad = np.radians(angles)
        mean_sin = np.mean(np.sin(angles_rad))
        mean_cos = np.mean(np.cos(angles_rad))

        circular_mean = np.degrees(np.arctan2(mean_sin, mean_cos))
        circular_mean = (circular_mean + 360) % 360

        R = np.sqrt(mean_sin**2 + mean_cos**2)
        circular_std = np.degrees(np.sqrt(-2 * np.log(R))) if R > 0.0001 else 0.0

        return {
            "circular_mean": circular_mean,
            "circular_std": circular_std,
            "resultant_length": R
        }


def convert_numpy_types(obj: Any) -> Any:
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    return obj


# Singleton instances (lazy loading)
_coordinate_converter: Optional[CoordinateConverter] = None
_geometry_calculator: Optional[GeometryCalculator] = None
_color_mapper: Optional[ColorMapper] = None
_data_validator: Optional[DataValidator] = None
_statistics_calculator: Optional[StatisticsCalculator] = None

def get_coordinate_converter() -> CoordinateConverter:
    global _coordinate_converter
    if _coordinate_converter is None:
        _coordinate_converter = CoordinateConverter()
    return _coordinate_converter

def get_geometry_calculator() -> GeometryCalculator:
    global _geometry_calculator
    if _geometry_calculator is None:
        _geometry_calculator = GeometryCalculator()
    return _geometry_calculator

def get_color_mapper() -> ColorMapper:
    global _color_mapper
    if _color_mapper is None:
        _color_mapper = ColorMapper()
    return _color_mapper

def get_data_validator() -> DataValidator:
    global _data_validator
    if _data_validator is None:
        _data_validator = DataValidator()
    return _data_validator

def get_statistics_calculator() -> StatisticsCalculator:
    global _statistics_calculator
    if _statistics_calculator is None:
        _statistics_calculator = StatisticsCalculator()
    return _statistics_calculator
