"""
Seismicity Migration Analysis Configuration Module

This module contains all configuration parameters and settings for the
seismicity migration analysis tool.
"""

import os
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
import json
import logging

logger = logging.getLogger(__name__)

# Basic configuration
@dataclass
class BaseConfig:
    """Basic configuration class"""
    DATA_DIR: str = "data"
    FIGURE_DIR: str = "figures"
    WGS84_PROJ_STRING: str = "+proj=longlat +datum=WGS84 +no_defs"
    WEB_MERCATOR_PROJ_STRING: str = "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs"
    MIN_MAGNITUDE: float = 0.0
    MAX_MAGNITUDE: float = 10.0
    MIN_DISTANCE_KM: float = 0.1
    MAX_DISTANCE_KM: float = 1000.0
    HIST_BINS: int = 36
    HIST_RANGE: Tuple[int, int] = (0, 360)
    GAUSSIAN_PEAK_THRESHOLD: float = 0.3
    GAUSSIAN_MIN_DISTANCE: int = 5
    FIGURE_SIZE: Tuple[int, int] = (12, 8)
    DPI: int = 300
    FONT_SIZE: int = 12
    COLOR_MAP: str = "viridis"

@dataclass
class CatalogConfig:
    """Earthquake catalog configuration class"""
    SUPPORTED_FORMATS: List[str] = field(default_factory=lambda: [
        "csv", "txt", "dat", "sample", "ridgecrest", "wenchuan",
        "turkey", "synthetic", "srcmod"
    ])
    COLUMN_MAPPING: Dict[str, List[str]] = field(default_factory=lambda: {
        "longitude": ["lon", "longitude", "long", "x", "easting"],
        "latitude": ["lat", "latitude", "y", "northing"],
        "magnitude": ["mag", "magnitude", "mw", "ml", "ms"],
        "depth": ["depth", "dep", "z", "elevation"],
        "time": ["time", "datetime", "date", "timestamp"]
    })
    TIME_FORMATS: List[str] = field(default_factory=lambda: [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y%m%d%H%M%S"
    ])

@dataclass
class VisualizationConfig:
    """Visualization configuration class"""
    COLORS: Dict[str, str] = field(default_factory=lambda: {
        "primary": "#1f77b4", "secondary": "#ff7f0e", "success": "#2ca02c",
        "danger": "#d62728", "warning": "#ff7f0e", "info": "#17becf",
        "light": "#f8f9fa", "dark": "#343a40"
    })
    MARKERS: Dict[str, str] = field(default_factory=lambda: {
        "earthquake": "o", "peak": "^", "gaussian": "--", "mean": "|"
    })
    LINE_STYLES: Dict[str, str] = field(default_factory=lambda: {
        "solid": "-", "dashed": "--", "dotted": ":", "dashdot": "-."
    })

@dataclass
class Config:
    """Main configuration class"""
    base: BaseConfig = field(default_factory=BaseConfig)
    catalog: CatalogConfig = field(default_factory=CatalogConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)

    def __post_init__(self):
        """Create directories after initialization."""
        self._create_directories()

    def _create_directories(self):
        """Create necessary directories"""
        for directory in [self.base.DATA_DIR, self.base.FIGURE_DIR]:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                logger.warning(f"Could not create directory {directory}: {e}")

    def load_config(self, config_file: str):
        """Load configuration from file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            self._update_config(config_data)
        except Exception as e:
            logger.error(f"Failed to load configuration file {config_file}: {e}")
            logger.warning("Using default configuration")

    def _update_config(self, config_data: Dict[str, Any]):
        """Update configuration data"""
        for config_key, config_values in config_data.items():
            if hasattr(self, config_key) and isinstance(config_values, dict):
                config_section = getattr(self, config_key)
                for key, value in config_values.items():
                    if hasattr(config_section, key):
                        setattr(config_section, key, value)

    def save_config(self, config_file: str):
        """Save configuration to file"""
        try:
            config_data = {
                "base": self.base.__dict__,
                "catalog": self.catalog.__dict__,
                "visualization": self.visualization.__dict__
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save configuration file {config_file}: {e}")

    def get_catalog_formats(self) -> List[str]:
        return self.catalog.SUPPORTED_FORMATS.copy()

    def get_column_mapping(self) -> Dict[str, List[str]]:
        return self.catalog.COLUMN_MAPPING.copy()

    def get_time_formats(self) -> List[str]:
        return self.catalog.TIME_FORMATS.copy()

# Global configuration instance
_config: Optional[Config] = None

def get_config() -> Config:
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = Config()
    return _config

def set_config(new_config: Config):
    """Set global configuration instance"""
    global _config
    _config = new_config
