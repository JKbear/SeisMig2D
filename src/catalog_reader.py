"""
Seismic Catalog Reader Module (Refactored & Simplified)

This module provides functions for reading and parsing seismic catalog formats.
- CSVCatalogReader: Handles CSV files with headers.
- TextCatalogReader: Handles text files with a fixed 10-column format.
"""

import os
import re
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union, Tuple, Any
from dataclasses import dataclass, field

# Assuming config and utils are in the same src directory
from src.config import get_config
from src.utils import get_data_validator

# --- Configuration and Global Tools ---
config = get_config()
validator = get_data_validator()
logger = logging.getLogger(__name__)

# --- Data Model ---
@dataclass
class EarthquakeEvent:
    """Data class for a single earthquake event"""
    longitude: float
    latitude: float
    magnitude: float
    depth: float = 0.0
    time: Optional[datetime] = None
    time_str: Optional[str] = None
    event_id: Optional[str] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)

# --- Base Reader Class ---
class BaseCatalogReader:
    """Base class for seismic catalog readers"""

    def __init__(self):
        """Initialize the reader"""
        self.column_mapping: Dict[str, List[str]] = config.get_column_mapping()
        self.time_formats: List[str] = config.get_time_formats()

    def read_file(self, file_path: str, **kwargs: Any) -> List[EarthquakeEvent]:
        """Read earthquake catalog file (must be implemented by subclasses)"""
        raise NotImplementedError("Subclass must implement this method")

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """Parse a time string using a list of predefined formats."""
        if not isinstance(time_str, str):
            return None
        for fmt in self.time_formats:
            try:
                return datetime.strptime(time_str.strip(), fmt)
            except (ValueError, TypeError):
                continue
        logger.warning(f"Time string '{time_str}' could not be parsed with any known format.")
        return None

    def _create_event_from_dict(self, data: Dict[str, Any], line_info: str = "") -> Optional[EarthquakeEvent]:
        """
        Core helper function:
        Creates and validates an EarthquakeEvent object from a data dictionary.
        """
        try:
            event = EarthquakeEvent(
                longitude=float(data.get('longitude', 0)),
                latitude=float(data.get('latitude', 0)),
                magnitude=float(data.get('magnitude', 0)),
                depth=float(data.get('depth', 0)),
                time_str=str(data.get('time', ''))
            )

            # Handle time parsing
            if event.time_str:
                event.time = self._parse_time(event.time_str)
            # Handle time parts from TextCatalogReader
            elif all(k in data for k in ['year', 'month', 'day', 'hour', 'minute', 'second']):
                try:
                    # Attempt to build a standard time string
                    time_str_from_parts = (
                        f"{int(data['year']):04d}-{int(data['month']):02d}-{int(data['day']):02d} "
                        f"{int(data.get('hour', 0)):02d}:{int(data.get('minute', 0)):02d}:{float(data.get('second', 0)):06.3f}"
                    )
                    event.time = self._parse_time(time_str_from_parts)
                    event.time_str = time_str_from_parts
                except (ValueError, TypeError):
                    logger.warning(f"Could not assemble date/time from parts: {data}")

            event.additional_info = data

            # Unified validation
            if not validator.validate_coordinates(event.latitude, event.longitude) or \
               not validator.validate_magnitude(event.magnitude) or \
               not validator.validate_depth(event.depth):
                logger.warning(f"Skipping invalid event data (from {line_info}): {data}")
                return None

            return event

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Failed to create event from data dict (from {line_info}): {data}. Error: {e}")
            return None

# --- CSV Reader ---
class CSVCatalogReader(BaseCatalogReader):
    """CSV catalog reader (header-based)"""

    def read_file(self, file_path: str, **kwargs: Any) -> List[EarthquakeEvent]:
        """Reads a CSV format catalog"""
        try:
            # Assume CSV always has a header row
            header = kwargs.pop('header', 0)
            df = pd.read_csv(file_path, header=header, on_bad_lines='skip', **kwargs)
            df = self._normalize_columns(df)

            events: List[EarthquakeEvent] = []
            for index, row in df.iterrows():
                # Call the unified base class method
                event = self._create_event_from_dict(row.to_dict(), line_info=f"CSV Row {index + 2}")
                if event:
                    events.append(event)
            return events

        except Exception as e:
            logger.error(f"Failed to read CSV file {file_path}: {e}", exc_info=True)
            raise ValueError(f"Failed to read CSV file {file_path}: {e}")

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names based on the config mapping."""
        column_map: Dict[str, str] = {}
        for standard_name, variations in self.column_mapping.items():
            for col in df.columns:
                if str(col).lower().strip() in [v.lower() for v in variations]:
                    column_map[str(col)] = standard_name
                    break
        return df.rename(columns=column_map)

# --- Text Reader ---
class TextCatalogReader(BaseCatalogReader):
    """
    Simplified text file reader.
    Supports only one fixed 10-column format:
    Year Month Day Hour Minute Second Lon Lat Mag Dep
    (Assumed to be whitespace-delimited)
    """

    # Define the fixed column order
    FIXED_COLUMN_ORDER = [
        'year', 'month', 'day', 'hour', 'minute', 'second',
        'longitude', 'latitude', 'magnitude', 'depth'
    ]

    def read_file(self, file_path: str, **kwargs: Any) -> List[EarthquakeEvent]:
        """
        Reads a text file using the fixed 10-column order.
        """
        events: List[EarthquakeEvent] = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    parts = line.split()

                    if len(parts) < len(self.FIXED_COLUMN_ORDER):
                        logger.warning(
                            f"Skipping line #{line_num}: Not enough columns "
                            f"(Need {len(self.FIXED_COLUMN_ORDER)}, found {len(parts)}). "
                            f"Line: '{line}'"
                        )
                        continue

                    try:
                        # Map the split parts to the fixed column names
                        data = dict(zip(self.FIXED_COLUMN_ORDER, parts))

                        # Call the unified base class method
                        event = self._create_event_from_dict(data, line_info=f"Text Row {line_num}")
                        if event:
                            events.append(event)

                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse line #{line_num}: {line}. Error: {e}")

            return events
        except Exception as e:
            logger.error(f"Failed to read text file {file_path}: {e}", exc_info=True)
            raise ValueError(f"Failed to read text file {file_path}: {e}")

# --- Reader Factory ---
class CatalogReaderFactory:
    """
    Simplified factory. Selects reader based on file extension only.
    No longer supports 'format_hint'.
    """
    @staticmethod
    def create_reader(file_path: str) -> BaseCatalogReader:
        """Create the appropriate reader based on file extension."""
        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.csv':
            return CSVCatalogReader()
        elif ext in ['.txt', '.dat', '.asc']:
            return TextCatalogReader()
        else:
            logger.info(f"Unknown file extension '{ext}', defaulting to CSVCatalogReader.")
            return CSVCatalogReader()

    @staticmethod
    def read_catalog(file_path: str, **kwargs: Any) -> List[EarthquakeEvent]:
        """
        Convenience function to read a catalog.
        """
        reader = CatalogReaderFactory.create_reader(file_path)
        return reader.read_file(file_path, **kwargs)

# --- External Interface and Filter Functions ---

# Public convenience function
read_earthquake_catalog = CatalogReaderFactory.read_catalog

def filter_events_by_magnitude(
    events: List[EarthquakeEvent],
    min_mag: Optional[float] = None,
    max_mag: Optional[float] = None
) -> List[EarthquakeEvent]:
    """Filter a list of events by magnitude."""
    filtered = events
    if min_mag is not None:
        filtered = [e for e in filtered if e.magnitude >= min_mag]
    if max_mag is not None:
        filtered = [e for e in filtered if e.magnitude <= max_mag]
    return filtered

def filter_events_by_time(
    events: List[EarthquakeEvent],
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> List[EarthquakeEvent]:
    """Filter a list of events by time."""
    filtered = events
    if start_time is not None:
        filtered = [e for e in filtered if e.time and e.time >= start_time]
    if end_time is not None:
        filtered = [e for e in filtered if e.time and e.time <= end_time]
    return filtered

def filter_events_by_region(
    events: List[EarthquakeEvent],
    min_lon: float, max_lon: float,
    min_lat: float, max_lat: float
) -> List[EarthquakeEvent]:
    """Filter a list of events by geographic region."""
    return [
        e for e in events
        if min_lon <= e.longitude <= max_lon and min_lat <= e.latitude <= max_lat
    ]
