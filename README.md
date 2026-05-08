# SeisMig2D — Seismic Migration Direction Analysis Tool v4

## Project Overview

SeismicityMigration is a scientific computing tool for analyzing seismic activity migration patterns. This tool can read seismic catalog data in multiple formats, calculate azimuth distributions between earthquake pairs, detect dominant migration directions, and provide rich visualization capabilities.

## Main Features

### 🔍 Seismic Catalog Reading
- Support for multiple data formats: CSV, text files
- Automatic format detection and parsing
- Data validation and quality control

### 📊 Directional Analysis
- Calculate directivity angles and distances between earthquake event pairs
- Von Mises Mixture Model (vMMM) fitting for circular data
- Circular statistics (mean direction, concentration κ)
- Automatic peak detection and multi-component fitting

### 🔬 Statistical Modeling (NEW 2026-05-09)
- **Von Mises Mixture Model (vMMM)**: replaces single-Gaussian-per-peak with global K-component mixture
- Proper handling of circular topology (0° = 360°)
- Simultaneous fitting of all components via L-BFGS-B optimisation
- κ (concentration) and σ-equivalent per component
- SEP inter-event time & speed physical interpretation: [docs/SEP_physical_interpretation.md](docs/SEP_physical_interpretation.md)

### 🗺️ Spatial Analysis
- Epicenter distribution visualization
- Spatial density analysis
- Coordinate conversion (WGS84 ↔ Web Mercator)

### ⏰ Time Series Analysis
- Magnitude-time series analysis
- Migration direction evolution over time
- Time window analysis

### 🔀 Temporal Ratio Analysis (NEW)
- Sliding-window N2/N1 ratio evolution
- Peak region counting and ratio calculation
- 95% confidence interval under null hypothesis
- Multi-window comparison with log-scale plots

### ⚡ SEP Dtime & Speed Analysis (NEW)
- Inter-event time (dtime) statistics per pair
- Migration speed (km/s) per pair
- Ping-pong effect filter (min_dtime_seconds)
- Dtime/speed histograms and time-evolution scatter plots

### 📈 Visualization Features
- Static graphics: histograms, polar plots, epicenter distribution maps
- Interactive visualizations (requires Plotly)
- Comprehensive analysis dashboard
- Support for multiple output formats (SVG, PDF, PNG)
- 10+ plot types including ratio evolution, peak region histograms, dtime/speed evolution

### 🤖 Machine Learning (planned)
- Seismic activity pattern recognition
- Dimensionality reduction and feature extraction

## Project Structure

```
SeisMig2D/
├── src/                          # Source code
│   ├── __init__.py              # Package init
│   ├── config.py                # Configuration management
│   ├── utils.py                 # Utility functions (coordinate conversion, validation, statistics)
│   ├── catalog_reader.py        # Earthquake catalog readers (CSV and fixed-format text)
│   ├── seismic_analyzer.py      # Core analysis (directivity, histogram, peaks, Gaussian fitting)
│   ├── visualizer.py            # Matplotlib + Plotly visualizations
├── data/                        # Sample data files
├── figures/                     # Output figures directory
├── main.py                      # CLI entry point
├── requirements.txt             # Dependencies
├── README.md                    # Project documentation
├── USER_GUIDE.md                # Detailed user guide
├── LICENSE                      # MIT License
├── examples/                    # Example scripts
└── tests/                       # Test suite

```

## Installation Instructions

### System Requirements
- Python 3.8 or higher
- Windows/Linux/macOS operating systems

### Quick Installation
```bash
# Clone the project
git clone https://github.com/JKbear/SeisMig2D.git
cd SeisMig2D

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Optional Dependencies
For interactive visualization, install Plotly:
```bash
pip install plotly>=5.0.0
```

## Usage

### Basic Usage
```bash
# Analyze single seismic catalog file
python main.py -i data/earthquakes.csv -o results/

# Use custom configuration
python main.py -i data/earthquakes.csv -c config.json -o results/
```

### Advanced Usage
```bash
# Batch processing mode (process entire directory)
python main.py -i data/ --batch -o results/

# Specify magnitude and time range
python main.py -i data/earthquakes.csv -o results/ --min-mag 4.0 --start-date "2020-01-01" --end-date "2023-12-31"

# Complete analysis with temporal/spatial/magnitude analysis (slower)
python main.py -i data/earthquakes.csv -o results/ --full-analysis

# Temporal sliding ratio analysis (N2/N1 ratio over time)
python main.py -i data/earthquakes.csv -o results/ --temporal-ratio
python main.py -i data/earthquakes.csv -o results/ --temporal-ratio --ratio-window-sizes "7,30,60,90,120" --ratio-time-step 1

# Filter concurrent event pairs (ping-pong effect)
python main.py -i data/earthquakes.csv -o results/ --min-dtime 10

# Generate interactive visualizations
python main.py -i data/earthquakes.csv -o results/ --interactive
```

### 命令行参数
```
参数说明:
  -i, --input          输入文件或目录路径（必需）
  -o, --output         输出目录路径（默认: output/）
  -c, --config         配置文件路径（JSON格式，可选）
  
  # 分析参数
  --min-mag            最小震级阈值
  --max-mag            最大震级阈值
  --start-date         开始日期（格式: YYYY-MM-DD）
  --end-date           结束日期（格式: YYYY-MM-DD）
  
  # 分析类型
  --directivity-only       仅执行方向分析（默认）
  --full-analysis          执行完整分析（含时空震级）
  --temporal-ratio         启用时序滑动窗口比率分析（N2/N1）
  
  # 时序比率参数
  --ratio-window-sizes     窗口尺寸列表，逗号分隔（如 "7,30,60,90,120"）
  --ratio-time-step        步长天数（默认: 0.5）
  --peak-half-width        峰值区域半宽，度（默认: 30）
  --ratio-min-events       最小事件对数阈值（默认: 10）
  
  # 反乒乓滤波
  --min-dtime              最小时间间隔秒数（默认: 10，设为0关闭）
  
  # 可视化选项
  --no-plots               不生成图形
  --interactive            生成交互式可视化
  --plot-format            图形格式（svg/pdf/png）
  
  # 其他选项
  --batch                  批处理模式
  --debug                  启用调试模式
  --quiet                  静默模式
```

## Data Formats
Data Formats
The tool supports two simplified data formats:

1. CSV Format (.csv)
Must contain a header row.

Columns are automatically mapped based on names defined in config.py (e.g., latitude, lon, mag are recognized).

Example events.csv:

latitude,longitude,depth,magnitude,time
35.123,120.456,10.5,4.2,2023-01-01T12:30:45
35.234,120.567,8.3,3.8,2023-01-01T13:15:20
2. Fixed-Format Text (.txt, .dat, .asc)
Must NOT contain a header row.
Must follow a strict 10-column order, separated by whitespace.
Lines starting with # are treated as comments and skipped.
Required Column Order:

Year  Month Day Hour  Minute  Second  Longitude Latitude  Magnitude Depth

Example events.txt:

# Format: YYYY MM DD HH MM SS LON LAT MAG DEP
2023 01 01 12 00 00 -118.20 35.50 4.5 10.0
2023 01 01 13 30 00 -118.21 35.51 3.8 8.5

## Configuration File

The configuration file uses JSON format. Valid top-level keys are `base`, `catalog`, and `visualization`:

```json
{
  "base": {
    "HIST_BINS": 36,
    "HIST_RANGE": [0, 360],
    "GAUSSIAN_PEAK_THRESHOLD": 0.3,
    "GAUSSIAN_MIN_DISTANCE": 5,
    "FIGURE_SIZE": [12, 8],
    "DPI": 300,
    "FONT_SIZE": 12,
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

## Output Results

### Analysis Result Files
- `*_analysis_results.json`: Detailed analysis results (JSON format)
- `batch_analysis_summary.json`: Batch processing summary report

### Visualization Files
- `*_directivity_histogram.svg`: Azimuth histogram
- `*_polar_histogram.svg`: Polar azimuth plot
- `*_epicenter_map.svg`: Epicenter distribution map
- `*_analysis_dashboard.svg`: Comprehensive analysis dashboard
- `*_interactive_map.html`: Interactive epicenter distribution map (optional)
- `*_interactive_histogram.html`: Interactive azimuth histogram (optional)

## Algorithm Description

### Azimuth Calculation
Using spherical trigonometry to calculate the azimuth between two earthquake events:
```
θ = atan2(sin(Δλ) * cos(φ2), cos(φ1) * sin(φ2) - sin(φ1) * cos(φ2) * cos(Δλ))
```

### Gaussian Fitting
Using nonlinear least squares method to fit Gaussian functions:
```
f(x) = A * exp(-(x-μ)²/(2σ²))
```

### Peak Detection
Using the `peakutils` library to automatically detect peaks in histograms, supporting multiple detection algorithms.

## Performance Optimization

- **Vectorized computation**: Using NumPy for efficient array operations
- **Caching mechanism**: Caching frequently used calculation results
- **Parallel processing**: Support for multi-threading (future version)

## Error Handling

The program includes comprehensive error handling mechanisms:
- Data validation and cleaning
- Exception capture and logging
- User-friendly error messages
- Automatic recovery mechanisms

## Development Guide

### Adding New Data Format Support
1. Create a new reader class in `catalog_reader.py`
2. Inherit from the `BaseCatalogReader` base class
3. Implement the `read_file` method
4. Register the new reader in `CatalogReaderFactory`

### Adding New Analysis Algorithms
1. Create a new analyzer class in `seismic_analyzer.py`
2. Implement the analysis logic
3. Add result data classes
4. Update the main program interface

### Adding New Visualization Types
1. Create a new visualizer class in `visualizer.py`
2. Inherit from the `BaseVisualizer` base class
3. Implement plotting methods
4. Add convenience functions

## Testing

Run test suite:
```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest tests/

# Run specific tests
pytest tests/test_catalog_reader.py

# Generate test coverage report
pytest --cov=src tests/
```

## Contribution Guidelines

1. Fork the project repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add some amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Create Pull Request

### Code Standards
- Follow PEP 8 coding standards
- Use type annotations
- Write unit tests
- Add docstrings

## License

This project uses the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

If you use this tool for research, please cite:
```
SeismicityMigration: A Python Tool for Earthquake Migration Analysis
[Author Information]
[Year]
```

## Contact Information

- Project Maintainer: Ke JIA
- Email: jk@nwpu.edu.cn
- Project Homepage: github.com/JKbear/SeisMig2D

## Changelog

### v4.1.0 (2026-05-09)
- 🔬 **von Mises Mixture Model**: replace per-peak Gaussian with K-component vMMM for circular data
- 🔀 **Temporal ratio analysis**: sliding-window N2/N1 ratio with 95% CI, multi-window comparison
- ⚡ **SEP dtime & speed**: inter-event time and migration speed per pair, histograms + evolution plots
- 🛡️ **Ping-pong filter**: `--min-dtime` flag removes concurrent event pairs (default 10s)
- 📊 **Peak region histograms**: blue/red fill_between highlights, N2/N1 ratio annotations
- 🎨 **Visual overhaul**: gist_rainbow colormap, white background, black borders, dashed grids
- 🏷️ **Naming**: bearing → directivity throughout codebase
- 📝 **Documentation**: [SEP physical interpretation](docs/SEP_physical_interpretation.md), CLAUDE.md, updated README & USER_GUIDE
- 🧹 **Code quality**: extract _gaussian, combine filter masks, searchsorted optimization, remove dead code
- 📦 **Data**: fixed-format catalogs for Wenchuan (HuangWuFang & ChenJiuhui), Changning, Ridgecrest, Turkey

### v4.0.0
- 🔧 Default mode changed to directivity-only (fast path); use `--full-analysis` for comprehensive analysis
- 🐛 Fixed b-value estimation (5th percentile Mc, Aki-Utsu MLE method)
- 🐛 Fixed save_figure file extension bug
- 🐛 Fixed hardcoded bar widths in histograms (now adaptive)
- 🧹 Removed unused dependencies (seaborn, pyyaml, tqdm, python-dateutil)
- 📚 Rewritten examples to match actual API
- 📄 Added MIT LICENSE file
- ⚡ Performance warnings for large temporal analysis windows

### v3.0.0
- 🔧 Complete code structure refactoring
- 📊 Enhanced visualization features
- 🚀 Performance optimization with vectorized directivity calculation
- 🐛 Fixed known issues
- 📚 Improved documentation

### v2.0.0
- 📊 Added temporal analysis and spatial analysis
- 🎨 Added polar histogram and interactive visualizations

### v1.0.0
- ✨ Initial version release
- 📖 Basic directivity analysis and Gaussian fitting

## Acknowledgments

Thanks to all contributors and testers for their support!

