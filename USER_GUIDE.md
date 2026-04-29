# Seismic Migration Analysis Tool - User Guide

## Overview

This tool analyzes seismic migration patterns in earthquake catalogs. It can:
- Calculate bearing (azimuth) angles between earthquake pairs
- Analyze temporal evolution of seismicity
- Perform spatial and magnitude analysis
- Detect dominant migration directions using Gaussian fitting
- Generate migration statistics and visualizations

## Installation

### Requirements
- Python 3.8 or higher
- Required packages listed in `requirements.txt`

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Optional: For interactive visualizations
pip install plotly>=5.0.0
```

## Usage Methods

This tool can be used in two ways:
1. **Command-line interface** - For batch processing and automation
2. **Python API** - For custom analysis and integration

## Command-Line Interface

### Basic Usage
```bash
# Analyze single earthquake catalog file
python main.py -i data/earthquakes.csv -o results/

# Use custom configuration file
python main.py -i data/earthquakes.csv -c config.json -o results/
```

### Advanced Usage
```bash
# Batch processing mode (process entire directory, max 5 files)
python main.py -i data/ --batch -o results/

# Specify magnitude and time range filters
python main.py -i data/earthquakes.csv -o results/ --min-mag 4.0 --start-date "2020-01-01" --end-date "2023-12-31"

# Bearing analysis only (faster, no temporal analysis)
python main.py -i data/earthquakes.csv -o results/ --bearing-only

# Full analysis (including migration analysis)
python main.py -i data/earthquakes.csv -o results/ --full-analysis

# Generate interactive visualizations (requires plotly)
python main.py -i data/earthquakes.csv -o results/ --interactive

# Specify plot format
python main.py -i data/earthquakes.csv -o results/ --plot-format png

# Suppress plots (analysis only)
python main.py -i data/earthquakes.csv -o results/ --no-plots
```

### Command-Line Options

**Input/Output:**
- `-i, --input`: Input file or directory path (required)
- `-o, --output`: Output directory path (default: `output/`)
- `-c, --config`: Configuration file path (JSON format, optional)

**Analysis Parameters:**
- `--min-mag`: Minimum magnitude threshold
- `--max-mag`: Maximum magnitude threshold
- `--start-date`: Start date filter (format: YYYY-MM-DD)
- `--end-date`: End date filter (format: YYYY-MM-DD)

**Analysis Types:**
- `--bearing-only`: Execute bearing analysis only
- `--full-analysis`: Execute full analysis (including migration analysis)

**Visualization Options:**
- `--no-plots`: Do not generate plots
- `--interactive`: Generate interactive visualizations (requires plotly)
- `--plot-format`: Plot format - `svg`, `pdf`, or `png` (default: `svg`)

**Other Options:**
- `--batch`: Batch processing mode
- `--debug`: Enable debug mode
- `--quiet`: Quiet mode (show only error messages)

## Python API Usage

### 1. Load Your Data

```python
from src.catalog_reader import CatalogReaderFactory
from src.seismic_analyzer import analyze_seismicity_migration

# Load earthquake catalog (returns list of EarthquakeEvent objects)
events = CatalogReaderFactory.read_catalog('your_catalog.csv')

# Alternative: using the convenience function
from src.catalog_reader import read_earthquake_catalog
events = read_earthquake_catalog('your_catalog.csv')
```

### 2. Basic Analysis

```python
# Run comprehensive migration analysis
results = analyze_seismicity_migration(
    events=events,
    min_distance_km=0.1,    # Minimum distance between events
    max_distance_km=1000.0, # Maximum distance between events  
    time_window_days=30      # Time window for temporal analysis
)

# Print summary
print(f"Total events analyzed: {results.summary_statistics['total_events']}")
print(f"Main migration directions: {results.summary_statistics['dominant_directions']}")
```

### 3. Individual Analysis Components

#### Bearing Analysis Only
```python
from src.seismic_analyzer import calculate_bearings

bearing_results = calculate_bearings(
    events=events,
    min_distance_km=0.1,
    max_distance_km=1000.0
)

# Access bearing statistics
stats = bearing_results.statistics
print(f"Mean bearing: {stats['mean_bearing']:.1f}°")
print(f"Circular standard deviation: {stats['circular_std']:.1f}°")
print(f"Total pairs: {stats['total_pairs']}")

# Access detected peaks and Gaussian fits
print(f"Number of peaks: {len(bearing_results.peaks)}")
print(f"Gaussian fits: {len(bearing_results.gaussian_fits)}")
```

#### Custom Analysis
```python
from src.seismic_analyzer import MigrationAnalyzer

analyzer = MigrationAnalyzer()

# Temporal analysis
temporal = analyzer.temporal_analysis(events, time_window_days=30)

# Spatial analysis  
spatial = analyzer.spatial_analysis(events)

# Magnitude analysis
magnitude = analyzer.magnitude_analysis(events)

# Comprehensive analysis (same as analyze_seismicity_migration)
results = analyzer.comprehensive_analysis(
    events=events,
    min_distance_km=0.1,
    max_distance_km=1000.0,
    time_window_days=30
)
```

### 4. Data Filtering

```python
from src.catalog_reader import (
    filter_events_by_magnitude, 
    filter_events_by_time,
    filter_events_by_region
)
from datetime import datetime

# Filter by magnitude
filtered = filter_events_by_magnitude(events, min_mag=4.0, max_mag=8.0)

# Filter by time
start = datetime(2020, 1, 1)
end = datetime(2023, 12, 31)
filtered = filter_events_by_time(events, start_time=start, end_time=end)

# Filter by geographic region
filtered = filter_events_by_region(
    events, 
    min_lon=-120.0, max_lon=-118.0,
    min_lat=35.0, max_lat=37.0
)
```

## Input Data Format

The tool supports two main data formats:

### 1. CSV Format (.csv)
CSV files **must contain a header row**. Column names are automatically recognized based on common variations:
- **Longitude**: `lon`, `longitude`, `long`, `x`, `easting`
- **Latitude**: `lat`, `latitude`, `y`, `northing`
- **Magnitude**: `mag`, `magnitude`, `mw`, `ml`, `ms`
- **Depth**: `depth`, `dep`, `z`, `elevation`
- **Time**: `time`, `datetime`, `date`, `timestamp`

Example CSV format:
```csv
time,latitude,longitude,depth,magnitude
2023-01-01 12:00:00,35.5,-118.2,10.0,4.5
2023-01-02 13:30:00,35.6,-118.3,8.5,3.8
```

**Supported time formats:**
- `YYYY-MM-DD HH:MM:SS`
- `YYYY-MM-DD HH:MM:SS.fff`
- `YYYY/MM/DD HH:MM:SS`
- `YYYY-MM-DDTHH:MM:SS`
- `YYYY-MM-DDTHH:MM:SS.fff`
- `YYYYMMDDHHMMSS`

### 2. Fixed-Format Text Files (.txt, .dat, .asc)
Text files **must NOT contain a header row** and must follow a strict 10-column order (whitespace-delimited):
```
Year  Month  Day  Hour  Minute  Second  Longitude  Latitude  Magnitude  Depth
```

Lines starting with `#` are treated as comments and skipped.

Example text format:
```
# Format: Year Month Day Hour Minute Second Lon Lat Mag Depth
2023  01  01  12  00  00  -118.20  35.50  4.5  10.0
2023  01  01  13  30  00  -118.21  35.51  3.8  8.5
```

### Data Validation
The tool automatically validates:
- **Coordinates**: Latitude must be between -90 and 90, longitude between -180 and 180
- **Magnitude**: Must be between -10 and 10
- **Depth**: Must be between -100 and 1000 km
Invalid events are skipped with warnings logged.

## Output Interpretation

### MigrationAnalysisResult Structure

The `MigrationAnalysisResult` object contains the following attributes:

```python
results = analyze_seismicity_migration(events)

# Summary statistics
results.summary_statistics = {
    'total_events': int,                    # Total number of events analyzed
    'analysis_parameters': {               # Parameters used in analysis
        'min_distance_km': float,
        'max_distance_km': float,
        'time_window_days': int
    },
    'dominant_directions': [                # Top 3 dominant directions
        {
            'mean': float,                  # Mean bearing angle (degrees)
            'std': float,                   # Standard deviation (degrees)
            'amplitude': float              # Gaussian amplitude
        },
        ...
    ]
}

# Temporal analysis
results.temporal_analysis = {
    'time_series_stats': {                  # Time difference statistics
        'mean': float,
        'std': float,
        'min': float,
        'max': float,
        'total_duration_days': float
    },
    'magnitude_stats': {                    # Magnitude statistics over time
        'mean': float,
        'std': float,
        'min': float,
        'max': float
    },
    'window_analysis': [                    # Sliding window analysis results
        {
            'time': datetime,
            'event_count': int,
            'mean_magnitude': float,
            'dominant_direction': float     # Dominant direction for this window
        },
        ...
    ]
}

# Spatial analysis
results.spatial_analysis = {
    'latitude_stats': {                     # Latitude distribution stats
        'mean': float, 'std': float, 'min': float, 'max': float, ...
    },
    'longitude_stats': {                    # Longitude distribution stats
        'mean': float, 'std': float, 'min': float, 'max': float, ...
    },
    'depth_stats': {                        # Depth distribution stats
        'mean': float, 'std': float, 'min': float, 'max': float, ...
    },
    'spatial_range': {
        'latitude_range': float,            # Latitude range in degrees
        'longitude_range': float            # Longitude range in degrees
    },
    'spatial_density': float                # Events per square kilometer
}

# Magnitude analysis
results.magnitude_analysis = {
    'magnitude_stats': {                   # Basic magnitude statistics
        'mean': float, 'std': float, 'min': float, 'max': float, ...
    },
    'magnitude_frequency': {
        'bins': [...],                      # Magnitude bin centers
        'frequency': [...],                 # Frequency counts
        'cumulative_frequency': [...]       # Cumulative frequency
    },
    'b_value_estimate': float               # Gutenberg-Richter b-value estimate
}

# Directional analysis (BearingAnalysisResult)
results.directional_analysis = BearingAnalysisResult(
    bearings=np.ndarray,                    # All calculated bearing angles (degrees)
    distances=np.ndarray,                   # Distances for each pair (km)
    weights=np.ndarray,                     # Weights for each pair
    histogram=np.ndarray,                   # Histogram counts
    bin_edges=np.ndarray,                   # Histogram bin edges
    bin_centers=np.ndarray,                 # Histogram bin centers
    peaks=np.ndarray,                       # Indices of detected peaks
    peak_properties={                       # Properties of detected peaks
        'peak_heights': [...],
        'peak_positions': [...],
        'peak_widths': [...]
    },
    gaussian_fits=[                         # Gaussian fit parameters
        {
            'amplitude': float,
            'mean': float,                  # Peak center (degrees)
            'std': float,                   # Peak width (degrees)
            'r_squared': float,             # Fit quality
            'peak_index': int,
            'x_data': np.ndarray,
            'y_data': np.ndarray,
            'y_fit': np.ndarray
        },
        ...
    ],
    statistics={                            # Bearing statistics
        'total_pairs': int,
        'mean_distance': float,
        'std_distance': float,
        'mean_weight': float,
        'n_peaks': int,
        'n_gaussian_fits': int,
        'mean_bearing': float,
        'std_bearing': float,
        'circular_mean': float,             # Circular mean (degrees)
        'circular_std': float,              # Circular standard deviation
        'resultant_length': float           # Resultant vector length (0-1)
    }
)
```

### BearingAnalysisResult (Standalone)

When using `calculate_bearings()` separately:

```python
bearing_results = calculate_bearings(events)

# Access attributes directly
print(f"Number of pairs: {len(bearing_results.bearings)}")
print(f"Mean bearing: {bearing_results.statistics['mean_bearing']:.1f}°")
print(f"Detected {len(bearing_results.peaks)} peaks")
print(f"Gaussian fits: {len(bearing_results.gaussian_fits)}")

# Access individual Gaussian fits
for i, fit in enumerate(bearing_results.gaussian_fits):
    print(f"Direction {i+1}: {fit['mean']:.1f}° ± {fit['std']:.1f}°")
```

### Key Parameters

- **Dominant Directions**: Primary migration orientations (top 3 from Gaussian fits)
- **B-value**: Gutenberg-Richter b-value estimate (seismic activity rate parameter)
- **Spatial Density**: Events per square kilometer
- **Circular Statistics**: Directional analysis metrics (circular mean, circular std, resultant length)
- **Peak Detection**: Automatically detected peaks in bearing histogram
- **Gaussian Fits**: Fitted Gaussian distributions for each detected peak

## Visualization

The tool provides comprehensive visualization functions for analysis results.

### Available Visualization Functions

#### Bearing Visualizations
```python
from src.visualizer import plot_bearing_histogram, plot_polar_histogram

# Cartesian bearing histogram with Gaussian fits
plot_bearing_histogram(
    bearing_results,
    title="Bearing Distribution",
    show_gaussian_fits=True,
    show_statistics=True,
    save_filename="bearing_histogram.svg"
)

# Polar (circular) bearing histogram
plot_polar_histogram(
    bearing_results,
    title="Polar Bearing Distribution",
    show_statistics=True,
    save_filename="polar_histogram.svg"
)
```

#### Spatial Visualizations
```python
from src.visualizer import plot_epicenter_map

# Epicenter distribution map
plot_epicenter_map(
    events,
    title="Earthquake Epicenters",
    show_magnitude=True,
    color_by_time=False,  # Set True to color by time instead of magnitude
    save_filename="epicenter_map.svg"
)
```

#### Comprehensive Dashboard
```python
from src.visualizer import create_analysis_dashboard

# Create multi-panel analysis dashboard
create_analysis_dashboard(
    events,
    analysis_result,
    title="Seismicity Migration Analysis Dashboard",
    save_filename="analysis_dashboard.svg"
)
```

#### Interactive Visualizations (requires plotly)
```python
from src.visualizer import ComprehensiveVisualizer

viz = ComprehensiveVisualizer()

# Interactive epicenter map
interactive_map = viz.interactive_viz.create_interactive_map(events)
interactive_map.write_html("interactive_map.html")

# Interactive bearing histogram
interactive_hist = viz.interactive_viz.create_interactive_histogram(bearing_results)
interactive_hist.write_html("interactive_histogram.html")
```

### Custom Plotting

You can also access the raw data for custom visualizations:

```python
import matplotlib.pyplot as plt
import numpy as np

# Access bearing data
bearings = bearing_results.bearings
weights = bearing_results.weights
bin_centers = bearing_results.bin_centers
histogram = bearing_results.histogram

# Create custom plot
plt.figure(figsize=(8, 6))
plt.bar(bin_centers, histogram, width=10, alpha=0.7)
plt.xlabel('Bearing (degrees)')
plt.ylabel('Frequency')
plt.title('Seismic Migration Directions')
plt.show()

# Plot Gaussian fits
for fit in bearing_results.gaussian_fits:
    x = fit['x_data']
    y = fit['y_fit']
    plt.plot(x, y, 'r-', linewidth=2, label=f"μ={fit['mean']:.1f}°")
plt.legend()
plt.show()
```

### Output Files

When using command-line interface or saving visualizations:
- `*_bearing_histogram.{format}`: Cartesian bearing histogram
- `*_polar_histogram.{format}`: Polar bearing histogram  
- `*_epicenter_map.{format}`: Epicenter distribution map
- `*_analysis_dashboard.{format}`: Comprehensive analysis dashboard
- `*_interactive_map.html`: Interactive epicenter map (if `--interactive` used)
- `*_interactive_histogram.html`: Interactive bearing histogram (if `--interactive` used)

Supported formats: `svg` (default), `pdf`, `png`

## Advanced Usage

### Custom Distance Ranges
Adjust distance thresholds based on your study area:
```python
# Regional study (large distances)
results = analyze_seismicity_migration(
    events, 
    min_distance_km=1.0, 
    max_distance_km=500.0
)

# Local study (small distances)  
results = analyze_seismicity_migration(
    events, 
    min_distance_km=0.01, 
    max_distance_km=10.0
)

# Very local study (meters to kilometers)
results = analyze_seismicity_migration(
    events, 
    min_distance_km=0.001, 
    max_distance_km=1.0
)
```

### Time Window Selection
Choose appropriate time windows for temporal analysis:
```python
from src.seismic_analyzer import MigrationAnalyzer

analyzer = MigrationAnalyzer()

# Short-term migration (days to weeks)
short_term = analyzer.temporal_analysis(events, time_window_days=7)

# Medium-term patterns (weeks to months)
medium_term = analyzer.temporal_analysis(events, time_window_days=30)

# Long-term patterns (months to years)
long_term = analyzer.temporal_analysis(events, time_window_days=90)
```

### Configuration Customization

The tool uses a configuration system that can be customized:

```python
from src.config import get_config, Config

# Get default configuration
config = get_config()

# Modify configuration programmatically
config.base.HIST_BINS = 72  # Use finer bins for bearing histogram
config.base.GAUSSIAN_PEAK_THRESHOLD = 0.2  # Lower threshold for more peaks
config.base.FIGURE_SIZE = (16, 10)  # Larger figures

# Or load from JSON file
config.load_config('custom_config.json')
```

Example configuration file (`config.json`):
```json
{
  "base": {
    "HIST_BINS": 36,
    "GAUSSIAN_PEAK_THRESHOLD": 0.3,
    "FIGURE_SIZE": [12, 8],
    "DPI": 300,
    "COLOR_MAP": "viridis"
  },
  "visualization": {
    "COLORS": {
      "primary": "#1f77b4",
      "secondary": "#ff7f0e"
    }
  }
}
```

### Batch Processing

Use command-line batch processing for multiple files:
```bash
# Process all supported files in a directory (max 5 files)
python main.py -i data/ --batch -o results/

# The tool will:
# - Process each file sequentially
# - Show progress and estimated time
# - Generate summary report: batch_analysis_summary.json
```

### Working with Large Catalogs

For large earthquake catalogs:
```python
# Filter events before analysis to reduce computation
from src.catalog_reader import filter_events_by_magnitude

# Only analyze significant events
significant_events = filter_events_by_magnitude(events, min_mag=3.0)

# Use bearing-only analysis for faster processing
bearing_results = calculate_bearings(
    significant_events,
    min_distance_km=1.0,    # Increase minimum distance
    max_distance_km=100.0    # Decrease maximum distance
)
```

## Troubleshooting

### Common Issues

1. **"At least 2 earthquake events are required"**
   - Ensure your catalog has multiple events
   - Check file loading succeeded
   - Verify filters haven't removed all events

2. **"Insufficient event pairs for analysis"**
   - Check your distance range (min_distance_km, max_distance_km)
   - Events may be too far apart or too close
   - Try adjusting distance thresholds

3. **Poor Gaussian fits or no peaks detected**
   - Your data may not have clear migration patterns
   - Try adjusting `GAUSSIAN_PEAK_THRESHOLD` in configuration
   - Check if magnitude/time filtering removed too many events
   - Ensure sufficient event pairs are available

4. **File loading errors**
   - Verify file format matches requirements (CSV with header, or fixed-format text)
   - Check column names match supported variations
   - Ensure time format is supported
   - Check for encoding issues (use UTF-8)

5. **Visualization errors**
   - Ensure matplotlib is installed: `pip install matplotlib`
   - For interactive visualizations, install plotly: `pip install plotly`
   - Check output directory permissions

6. **Memory issues with large catalogs**
   - Use magnitude filtering to reduce event count
   - Adjust distance ranges to reduce pair calculations
   - Process in smaller time windows
   - Consider using `--bearing-only` for faster analysis

### Performance Tips

- **Use appropriate distance ranges**: Too wide ranges increase computation time (O(n²) pairs)
- **Filter events early**: Apply magnitude/time filters before analysis
- **Use bearing-only mode**: Skip temporal analysis if not needed (`--bearing-only`)
- **Batch processing**: Process multiple files efficiently with `--batch` mode
- **Configuration**: Adjust histogram bins and peak detection thresholds based on your needs

### Getting Help

1. Check log file: `seismicity_migration.log` for detailed error messages
2. Enable debug mode: `python main.py ... --debug` for verbose output
3. Review examples: See `examples/` directory for usage patterns
4. Check source code docstrings: All functions have detailed documentation
5. Verify input data: Ensure format matches requirements

## Examples

See the `examples/` directory for complete analysis scripts:
- `basic_analysis.py` - Simple migration analysis example
- `quick_start.py` - Quick start guide
- `regional_study.py` - Regional scale application  
- `temporal_evolution.py` - Time-dependent analysis
- `spatial_patterns.py` - Spatial pattern analysis
- `interactive_demo.py` - Interactive visualization examples
- `run_all_examples.py` - Run all examples at once

## Command-Line Output

### Results File
Analysis results are saved as JSON:
- `*_analysis_results.json`: Contains analysis statistics and parameters

### Batch Summary
When using `--batch` mode:
- `batch_analysis_summary.json`: Summary of all processed files with success/failure status

### Logging
All operations are logged to:
- `seismicity_migration.log`: Detailed log of all operations

## Support

For issues or questions:
1. Check this guide and examples in `examples/` directory
2. Review docstrings in source code (all modules are well-documented)
3. Ensure input data format is correct (see Input Data Format section)
4. Verify Python environment setup (Python 3.8+, all dependencies installed)
5. Check log file for detailed error messages