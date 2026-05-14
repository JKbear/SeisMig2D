# SeisMig2D-v4 — Project Guidance

## Architecture

- `main.py` — CLI entry point, orchestration
- `src/config.py` — configuration, defaults
- `src/catalog_reader.py` — reads CSV/txt catalogs → `EarthquakeEvent` list
- `src/seismic_analyzer.py` — core analysis: `DirectivityAnalyzer`, `MigrationAnalyzer`
- `src/visualizer.py` — all plotting (matplotlib + plotly)
- `src/utils.py` — coordinate conversion, color mapping, validation
- `tests/` — pytest suite (47 tests), run with `python -m pytest tests/ -v`
- `figures/` — generated SVG plots
- `output/` — JSON analysis results
- `data/` — input catalogs (use `*_fixed.txt` versions; ISO-time 5-col files must be converted first)

## Key Conventions

- **Naming**: "directivity" not "bearing" — class names, function names, variables all use `directivity`/`directivities`
- **Colormap**: `twilight` (default) or `gist_rainbow` (fallback) for directional cyclic data, black edges (`'k'`)
- **Data format**: `year month day hour minute second lon lat mag depth` (10 columns, fixed for all `*_fixed.txt` files)
- **External data conversion**: ISO-time 5-col format (`time lon lat depth mag`) files must be converted to 10-col fixed format before use. Convert script pattern: parse ISO time, reorder columns to year-month-day-hour-minute-second-lon-lat-mag-depth.
- **Style**: white background, no seaborn, black borders, dashed gray grids

## Key Data Structures

- `DirectivityAnalysisResult` — directivities, distances, weights, dtimes_seconds, speeds, pair_times, histogram, bin_edges, bin_centers, peaks, gaussian_fits, statistics
- `TemporalDirectivityResult` — window_sizes, times_by_window, ratios_by_window, n_totals_by_window, ci_lower/upper_by_window, **mode** ("sliding"|"cumulative")
- `MigrationAnalysisResult` — temporal_analysis, spatial_analysis, directional_analysis, magnitude_analysis

## Ratio Analysis: Two Modes

### Sliding Window (`--temporal-ratio`, default)
Two independent parameters:
- **`window_sizes`** (days): temporal window length — how much data each window contains
- **`time_step`** (days): step between consecutive windows — how much the window moves

Each window slides across the catalog independently. Captures temporal variability. Ratio can fluctuate widely when event density is low.

### Cumulative Window (`--cumulative`)
One parameter:
- **`time_step`** (days): growth increment — window always starts from first event and grows

Window is always [t0, t0 + N×step]. Naturally smooth — ratio converges as more data is added. Matches the legacy `hist_gauss_v4_0904_polar_temporal.py` behaviour.

CLI: `--cumulative` overrides `--temporal-ratio`. Use `--cumulative-step` to set growth step (default 1.0 day).

## Key Features

1. **Temporal ratio analysis** — sliding (`--temporal-ratio`) and cumulative (`--cumulative`) modes for N2/N1 ratio evolution
2. **Peak region histograms** — blue/red fill_between highlighting peak areas with count annotations
3. **SEP dtime & speed** — inter-event times and migration speeds, stored per pair in `DirectivityAnalysisResult`
4. **Ping-pong filter** (`min_dtime_seconds=10`) — removes concurrent event pairs
5. **Peak count text** — positioned at centroid between two peaks via `ax.get_xaxis_transform()`
6. **Annotation placement** — left-aligned, left of peak for mean>100°, right of peak otherwise
7. **Polar** — cardinal labels at `rmax*1.12`, theta_zero='E', theta_direction=1
8. **vMMM fitting** — von Mises Mixture Model replaces per-peak Gaussian fitting (v4.1.1)

## Verification

- `python -m pytest tests/ -q` — must pass 47/47
- `python main.py -i data/Wenchuan_hypoDD_fixed.txt -o output/ --plot-format svg` — generates 7 plots
- `python main.py -i data/... --temporal-ratio` — sliding ratio, adds 3 more plots
- `python main.py -i data/... --cumulative --cumulative-step 1.0` — cumulative ratio mode
- Syntax: `python -m py_compile src/*.py main.py`
