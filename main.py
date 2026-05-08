"""
Seismicity Migration Analysis - Main Program

This is the main program for the SeismicityMigration project.
It provides a command-line interface for earthquake catalog analysis and visualization.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import json
from datetime import datetime
import numpy as np

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

from config import get_config, Config
from catalog_reader import (
    CatalogReaderFactory, filter_events_by_magnitude, filter_events_by_time, EarthquakeEvent
)
from seismic_analyzer import (
    analyze_seismicity_migration, calculate_directivities, DirectivityAnalysisResult,
    MigrationAnalysisResult, TemporalDirectivityResult, MigrationAnalyzer
)
from visualizer import (
    plot_directivity_histogram, plot_polar_histogram, plot_epicenter_map,
    create_analysis_dashboard, ComprehensiveVisualizer, DirectivityVisualizer,
    plot_dtime_histogram, plot_speed_histogram, plot_dtime_evolution, plot_speed_evolution
)
from utils import convert_numpy_types

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('seismicity_migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Seismicity Migration Analysis Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze single earthquake catalog file
    python main.py -i data/earthquakes.csv -o results/

    # Analyze multiple files and generate complete report
    python main.py -i data/ --batch -o results/ --full-analysis

    # Use custom configuration file
    python main.py -i data/earthquakes.csv -c config/custom_config.json -o results/

    # Specify time range and magnitude threshold
    python main.py -i data/earthquakes.csv -o results/ --min-mag 4.0 --start-date "2020-01-01" --end-date "2023-12-31"

    # Generate interactive visualizations
    python main.py -i data/earthquakes.csv -o results/ --interactive
        """
    )

    # Input/output parameters
    parser.add_argument('-i', '--input', required=True,
                       help='Input earthquake catalog file or directory path')
    parser.add_argument('-o', '--output', default='output/',
                       help='Output directory path (default: output/)')
    parser.add_argument('-c', '--config',
                       help='Configuration file path (JSON format)')

    # Analysis parameters
    parser.add_argument('--min-mag', type=float, default=None,
                       help='Minimum magnitude threshold (default: None)')
    parser.add_argument('--max-mag', type=float, default=None,
                       help='Maximum magnitude threshold (default: None)')
    parser.add_argument('--start-date',
                       help='Start date (format: YYYY-MM-DD)')
    parser.add_argument('--end-date',
                       help='End date (format: YYYY-MM-DD)')

    # Analysis types
    parser.add_argument('--directivity-only', action='store_true',
                       help='Execute directivity analysis only (this is the default)')
    parser.add_argument('--full-analysis', action='store_true',
                       help='Execute full analysis including temporal, spatial, and magnitude analysis (slower)')
    parser.add_argument('--temporal-ratio', action='store_true',
                       help='Enable temporal sliding ratio analysis (N2/N1 ratio over time)')
    parser.add_argument('--ratio-window-sizes', type=str, default=None,
                       help='Comma-separated window sizes in days (e.g., "0.5,1.0,1.5,2.0,2.5")')
    parser.add_argument('--ratio-time-step', type=float, default=None,
                       help='Time step between windows in days (default: 0.5)')
    parser.add_argument('--peak-half-width', type=int, default=None,
                       help='Half-width of peak region in degrees (default: 30)')
    parser.add_argument('--ratio-min-events', type=int, default=None,
                       help='Minimum events in window for ratio calculation (default: 10)')
    parser.add_argument('--min-dtime', type=float, default=None,
                       help='Minimum inter-event time in seconds to filter concurrent pairs (default: 10, set 0 to disable)')

    # Visualization options
    parser.add_argument('--no-plots', action='store_true',
                       help='Do not generate plots')
    parser.add_argument('--interactive', action='store_true',
                       help='Generate interactive visualizations (requires plotly)')
    parser.add_argument('--plot-format', choices=['svg', 'pdf', 'png'], default='svg',
                       help='Plot format (default: svg)')

    # Additional parameter parsing
    parser.add_argument('--batch', action='store_true',
                       help='Batch processing mode (process all files in directory, max 5 files, show detailed progress)')

    # Debug options
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')
    parser.add_argument('--quiet', action='store_true',
                       help='Quiet mode (show only error messages)')

    return parser.parse_args()

def setup_logging(debug: bool = False, quiet: bool = False):
    """Set up logging level"""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif quiet:
        logging.getLogger().setLevel(logging.ERROR)
    else:
        logging.getLogger().setLevel(logging.INFO)

def load_configuration(config_path: Optional[str] = None) -> Config:
    """Load configuration file"""
    config = get_config()
    if config_path and os.path.exists(config_path):
        logger.info(f"Loading configuration file: {config_path}")
        config.load_config(config_path)
    else:
        logger.info("Using default configuration")
    return config

def create_output_directory(output_dir: str) -> str:
    """Create output directory"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Creating output directory: {output_dir}")
        return output_dir
    except Exception as e:
        logger.error(f"Failed to create output directory: {e}")
        raise

def _load_and_filter_events(input_file: str, args: argparse.Namespace) -> Optional[List[EarthquakeEvent]]:
    """Loads, filters, and returns events."""
    logger.info("Reading earthquake catalog...")
    events = CatalogReaderFactory.read_catalog(input_file)
    logger.info(f"Successfully read {len(events)} earthquake events")

    if not events:
        logger.warning("No earthquake events found")
        return None

    # Apply filters
    logger.info("Applying event filters...")

    if args.min_mag is not None or args.max_mag is not None:
        events = filter_events_by_magnitude(events, args.min_mag, args.max_mag)
        logger.info(f"Remaining {len(events)} events after magnitude filtering")

    if args.start_date or args.end_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d') if args.start_date else None
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d') if args.end_date else None
        events = filter_events_by_time(events, start_date, end_date)
        logger.info(f"Remaining {len(events)} events after time filtering")

    if len(events) < 2:
        logger.warning("Insufficient events after filtering for directivity analysis")
        return None

    return events

def _run_analysis(events: List[EarthquakeEvent], args: argparse.Namespace) -> Tuple[Optional[DirectivityAnalysisResult], Optional[MigrationAnalysisResult], Optional[TemporalDirectivityResult]]:
    """Runs the requested seismic analysis.

    Analysis modes:
    - Default: directivity-only analysis (fast)
    - --full-analysis: comprehensive analysis including temporal, spatial, and magnitude analysis
    - --directivity-only: explicit directivity-only (same as default, provides clarity)
    - --temporal-ratio: sliding window N2/N1 ratio analysis
    """
    logger.info("Executing seismic activity analysis...")
    directivity_result: Optional[DirectivityAnalysisResult] = None
    analysis_result: Optional[MigrationAnalysisResult] = None
    temporal_ratio_result: Optional[TemporalDirectivityResult] = None

    if args.full_analysis:
        logger.info("Executing comprehensive migration analysis...")
        analysis_result = analyze_seismicity_migration(events)
        directivity_result = analysis_result.directional_analysis
    else:
        # Default: directivity-only analysis (fast path)
        logger.info("Executing directivity analysis...")
        min_dtime = args.min_dtime  # None → use config default (10s)
        directivity_result = calculate_directivities(events, min_dtime_seconds=min_dtime)

    if args.temporal_ratio:
        logger.info("Executing temporal sliding ratio analysis...")
        window_sizes = None
        if args.ratio_window_sizes:
            window_sizes = [float(x.strip()) for x in args.ratio_window_sizes.split(',')]
        analyzer = MigrationAnalyzer()
        temporal_ratio_result = analyzer.temporal_directivity_ratio_analysis(
            events,
            window_sizes=window_sizes,
            time_step=args.ratio_time_step,
            peak_half_width=args.peak_half_width,
            min_events=args.ratio_min_events,
        )

    return directivity_result, analysis_result, temporal_ratio_result

def _generate_visualizations(
    events: List[EarthquakeEvent],
    directivity_result: DirectivityAnalysisResult,
    analysis_result: Optional[MigrationAnalysisResult],
    temporal_ratio_result: Optional[TemporalDirectivityResult],
    file_prefix: str,
    output_dir: str,
    args: argparse.Namespace
) -> List[str]:
    """Generates and saves all requested plots."""
    logger.info("Generating visualizations...")
    visualizations: List[str] = []
    plot_format = args.plot_format

    try:
        # 1. Directivity angle histogram
        plot_directivity_histogram(
            directivity_result,
            title=f"Directivity Distribution - {file_prefix}",
            save_filename=f"{file_prefix}_directivity_histogram.{plot_format}"
        )
        visualizations.append(f"{file_prefix}_directivity_histogram.{plot_format}")

        # 2. Polar plot
        plot_polar_histogram(
            directivity_result,
            title=f"Polar Directivity Distribution - {file_prefix}",
            save_filename=f"{file_prefix}_polar_histogram.{plot_format}"
        )
        visualizations.append(f"{file_prefix}_polar_histogram.{plot_format}")

        # 3. Epicenter distribution map
        plot_epicenter_map(
            events,
            title=f"Earthquake Epicenters - {file_prefix}",
            save_filename=f"{file_prefix}_epicenter_map.{plot_format}"
        )
        visualizations.append(f"{file_prefix}_epicenter_map.{plot_format}")

        # 4. Comprehensive analysis dashboard
        if analysis_result:
            try:
                create_analysis_dashboard(
                    events, analysis_result,
                    title=f"Seismicity Migration Analysis - {file_prefix}",
                    save_filename=f"{file_prefix}_analysis_dashboard.{plot_format}"
                )
                visualizations.append(f"{file_prefix}_analysis_dashboard.{plot_format}")
            except Exception as e:
                logger.warning(f"Failed to generate analysis dashboard: {e}", exc_info=args.debug)

        # 5. Temporal ratio plots
        if temporal_ratio_result:
            try:
                dv = DirectivityVisualizer()
                # Ratio evolution plot
                dv.plot_directivity_ratio_evolution(
                    temporal_ratio_result,
                    title=f"Directivity Ratio Evolution - {file_prefix}",
                    save_filename=f"{file_prefix}_ratio_evolution.{plot_format}"
                )
                visualizations.append(f"{file_prefix}_ratio_evolution.{plot_format}")
                # Histogram with peak region highlights (full catalog)
                dv.plot_histogram_with_peak_regions(
                    directivity_result,
                    title=f"Directivity with Peak Regions - {file_prefix}",
                    save_filename=f"{file_prefix}_peak_region_histogram.{plot_format}"
                )
                visualizations.append(f"{file_prefix}_peak_region_histogram.{plot_format}")
                # Single best-window plot
                dv.plot_single_window_ratio(
                    temporal_ratio_result,
                    title=f"Directivity Ratio (Best Window) - {file_prefix}",
                    save_filename=f"{file_prefix}_ratio_single_window.{plot_format}"
                )
                visualizations.append(f"{file_prefix}_ratio_single_window.{plot_format}")
            except Exception as e:
                logger.warning(f"Failed to generate temporal ratio plots: {e}", exc_info=args.debug)

        # 6. Dtime and speed histograms
        try:
            plot_dtime_histogram(
                directivity_result,
                title=f"Inter-event Time - {file_prefix}",
                save_filename=f"{file_prefix}_dtime_histogram.{plot_format}"
            )
            visualizations.append(f"{file_prefix}_dtime_histogram.{plot_format}")

            plot_speed_histogram(
                directivity_result,
                title=f"Migration Speed - {file_prefix}",
                save_filename=f"{file_prefix}_speed_histogram.{plot_format}"
            )
            visualizations.append(f"{file_prefix}_speed_histogram.{plot_format}")

            plot_dtime_evolution(
                directivity_result,
                title=f"SEP Inter-event Time vs. Time - {file_prefix}",
                save_filename=f"{file_prefix}_dtime_evolution.{plot_format}"
            )
            visualizations.append(f"{file_prefix}_dtime_evolution.{plot_format}")

            plot_speed_evolution(
                directivity_result,
                title=f"SEP Speed vs. Time - {file_prefix}",
                save_filename=f"{file_prefix}_speed_evolution.{plot_format}"
            )
            visualizations.append(f"{file_prefix}_speed_evolution.{plot_format}")
        except Exception as e:
            logger.warning(f"Failed to generate dtime/speed histograms: {e}", exc_info=args.debug)

        # 7. Interactive visualizations
        if args.interactive:
            logger.info("Generating interactive visualizations...")
            try:
                comp_viz = ComprehensiveVisualizer()
                if hasattr(comp_viz, 'interactive_viz'):
                    interactive_map = comp_viz.interactive_viz.create_interactive_map(events)
                    interactive_hist = comp_viz.interactive_viz.create_interactive_histogram(directivity_result)

                    map_file = os.path.join(output_dir, f"{file_prefix}_interactive_map.html")
                    hist_file = os.path.join(output_dir, f"{file_prefix}_interactive_histogram.html")

                    interactive_map.write_html(map_file)
                    interactive_hist.write_html(hist_file)

                    visualizations.extend([
                        f"{file_prefix}_interactive_map.html",
                        f"{file_prefix}_interactive_histogram.html"
                    ])
            except ImportError:
                logger.warning("Plotly library not found. Skipping interactive visualizations.")
            except Exception as e:
                logger.warning(f"Failed to generate interactive visualizations: {e}", exc_info=args.debug)

    except Exception as e:
        logger.error(f"Error generating visualizations: {e}", exc_info=args.debug)
        raise  # Re-raise to be caught by process_single_file

    return visualizations

def _save_results(
    directivity_result: DirectivityAnalysisResult,
    analysis_result: Optional[MigrationAnalysisResult],
    temporal_ratio_result: Optional[TemporalDirectivityResult],
    events: List[EarthquakeEvent],
    output_dir: str,
    file_prefix: str,
    args: argparse.Namespace
) -> str:
    """Serializes and saves analysis results to a JSON file."""
    logger.info("Saving analysis results...")
    results_file = os.path.join(output_dir, f"{file_prefix}_analysis_results.json")

    serializable_results: Dict[str, Any] = {
        "input_file": f"{file_prefix}",
        "total_events_processed": len(events),
        "analysis_type": "full_analysis" if args.full_analysis else "directivity_only",
        "directivity_analysis": convert_numpy_types({
            "total_pairs": directivity_result.statistics.get('total_pairs'),
            "mean_directivity": directivity_result.statistics.get('mean_directivity'),
            "std_directivity": directivity_result.statistics.get('std_directivity'),
            "mean_dtime_seconds": directivity_result.statistics.get('mean_dtime_seconds'),
            "mean_speed_kms": directivity_result.statistics.get('mean_speed_kms'),
            "gaussian_fits": directivity_result.gaussian_fits if directivity_result.gaussian_fits else []
        })
    }

    if analysis_result:
        serializable_results["migration_analysis"] = convert_numpy_types({
            "dominant_directions": analysis_result.summary_statistics.get('dominant_directions'),
            "spatial_range": analysis_result.spatial_analysis.get('spatial_range'),
            "magnitude_stats": analysis_result.magnitude_analysis.get('magnitude_stats')
        })

    if temporal_ratio_result:
        serializable_results["temporal_ratio_analysis"] = convert_numpy_types({
            "window_sizes": temporal_ratio_result.window_sizes,
            "mean_ratio_by_window": temporal_ratio_result.statistics.get('mean_ratio_by_window'),
            "total_windows_computed": temporal_ratio_result.statistics.get('total_windows_computed'),
        })

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_results, f, indent=2, ensure_ascii=False)

    return results_file

def process_single_file(input_file: str, output_dir: str, config: Config,
                       args: argparse.Namespace) -> Dict[str, Any]:
    """
    Main workflow for processing a single file.
    Orchestrates loading, analysis, visualization, and saving.
    """
    logger.info(f"Processing file: {input_file}")

    try:
        # 1. Load and filter data
        events = _load_and_filter_events(input_file, args)
        if events is None:
            return {"status": "warning", "message": "No valid events after filtering"}

        # 2. Execute analysis
        directivity_result, analysis_result, temporal_ratio_result = _run_analysis(events, args)
        if directivity_result is None:
            logger.warning("Analysis returned no results.")
            return {"status": "warning", "message": "Analysis completed with no results"}

        # 3. Generate visualizations
        analysis_type = "full_analysis" if args.full_analysis else "directivity_only"
        if args.temporal_ratio:
            analysis_type += "_temporal_ratio"
        results: Dict[str, Any] = {
            "input_file": input_file,
            "total_events": len(events),
            "analysis_type": analysis_type,
            "visualizations": []
        }

        file_prefix = os.path.splitext(os.path.basename(input_file))[0]

        if not args.no_plots:
            try:
                results["visualizations"] = _generate_visualizations(
                    events, directivity_result, analysis_result, temporal_ratio_result,
                    file_prefix, output_dir, args
                )
            except Exception as e:
                logger.error(f"Error during visualization: {e}")
                results["visualization_error"] = str(e)

        # 4. Save results
        results_file_path = _save_results(
            directivity_result, analysis_result, temporal_ratio_result,
            events, output_dir, file_prefix, args
        )
        results["results_file"] = results_file_path

        logger.info(f"Analysis completed: {input_file}")
        return {"status": "success", "results": results}

    except Exception as e:
        logger.error(f"Error processing file {input_file}: {e}", exc_info=args.debug)
        return {"status": "error", "message": str(e), "input_file": input_file}

def process_batch(input_dir: str, output_dir: str, config: Config,
                 args: argparse.Namespace) -> List[Dict[str, Any]]:
    """Batch processing mode"""
    logger.info(f"Executing batch processing mode: {input_dir}")

    supported_extensions = ['.csv', '.txt', '.dat', '.cat']
    input_files: List[Path] = []
    for ext in supported_extensions:
        input_files.extend(Path(input_dir).glob(f"*{ext}"))

    if not input_files:
        logger.warning(f"No supported files found in {input_dir}")
        return []

    MAX_BATCH_FILES = 5
    if len(input_files) > MAX_BATCH_FILES:
        logger.warning(f"Found {len(input_files)} files, exceeding maximum limit {MAX_BATCH_FILES}, only processing first {MAX_BATCH_FILES} files")
        input_files = input_files[:MAX_BATCH_FILES]

    logger.info(f"Found {len(input_files)} files to process")

    results: List[Dict[str, Any]] = []
    start_time = datetime.now()

    for i, input_file in enumerate(input_files, 1):
        file_start_time = datetime.now()
        logger.info(f"Processing file {i}/{len(input_files)}: {input_file.name}")

        result = process_single_file(str(input_file), output_dir, config, args)
        results.append(result)

        file_end_time = datetime.now()
        file_duration = (file_end_time - file_start_time).total_seconds()

        if result["status"] == "error":
            logger.warning(f"File {input_file.name} processing failed, continuing with other files")
        elif result["status"] == "success":
            logger.info(f"File {input_file.name} processed successfully, took {file_duration:.1f} seconds")

        progress = (i / len(input_files)) * 100
        elapsed_time = (file_end_time - start_time).total_seconds()
        estimated_total = (elapsed_time / i) * len(input_files)
        remaining_time = estimated_total - elapsed_time

        logger.info(f"Overall progress: {progress:.1f}% ({i}/{len(input_files)}), "
                   f"Estimated remaining time: {remaining_time:.0f} seconds")

    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()
    logger.info(f"Batch processing total time: {total_duration:.1f} seconds")

    logger.info("Generating batch processing summary report...")
    summary_file = os.path.join(output_dir, "batch_analysis_summary.json")

    summary = {
        "total_files": len(input_files),
        "successful_files": len([r for r in results if r["status"] == "success"]),
        "failed_files": len([r for r in results if r["status"] == "error"]),
        "warning_files": len([r for r in results if r["status"] == "warning"]),
        "results": results,
        "timestamp": datetime.now().isoformat()
    }

    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(f"Batch processing completed, summary report: {summary_file}")
    return results

def main() -> int:
    """Main function"""
    args: Optional[argparse.Namespace] = None
    try:
        args = parse_arguments()
        setup_logging(args.debug, args.quiet)

        logger.info("=" * 60)
        logger.info("Seismicity Migration Analysis Tool")
        logger.info("=" * 60)

        config = load_configuration(args.config)
        output_dir = create_output_directory(args.output)

        if args.batch:
            results = process_batch(args.input, output_dir, config, args)
            successful = len([r for r in results if r["status"] == "success"])
            failed = len([r for r in results if r["status"] == "error"])

            logger.info("=" * 60)
            logger.info("Batch processing completed")
            logger.info(f"Successful: {successful}, Failed: {failed}")
            logger.info(f"Output directory: {output_dir}")

        else:
            if not os.path.exists(args.input):
                logger.error(f"Input file does not exist: {args.input}")
                return 1

            result = process_single_file(args.input, output_dir, config, args)

            if result["status"] == "success":
                logger.info("=" * 60)
                logger.info("Analysis completed")
                logger.info(f"Output directory: {output_dir}")
                logger.info(f"Results file: {result['results']['results_file']}")

                if result['results']['visualizations']:
                    logger.info("Generated visualization files:")
                    for viz in result['results']['visualizations']:
                        logger.info(f"  - {viz}")

            else:
                logger.error(f"Analysis failed: {result['message']}")
                return 1

        logger.info("=" * 60)
        return 0

    except KeyboardInterrupt:
        logger.info("User interrupted program")
        return 130
    except Exception as e:
        logger.error(f"Program execution failed: {e}")
        if args and args.debug:
            logger.exception("Detailed error information:")
        return 1

if __name__ == "__main__":
    sys.exit(main())
