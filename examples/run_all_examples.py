#!/usr/bin/env python3
"""
Run All Examples

Runs all example scripts in sequence and reports results.
"""

import os
import sys
import subprocess
import time
from datetime import datetime


def main():
    print("SeisMig2D v4 — Complete Example Suite")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    examples_dir = os.path.dirname(os.path.abspath(__file__))
    examples = [
        ("Quick Start", "quick_start.py"),
        ("Basic Analysis", "basic_analysis.py"),
        ("Temporal Evolution", "temporal_evolution.py"),
        ("Spatial Patterns", "spatial_patterns.py"),
        ("Regional Study", "regional_study.py"),
        ("Interactive Demo", "interactive_demo.py"),
    ]

    results = []
    total_start = time.time()

    for i, (name, script) in enumerate(examples, 1):
        script_path = os.path.join(examples_dir, script)
        print(f"[{i}/{len(examples)}] {name} ({script})")

        if not os.path.exists(script_path):
            print(f"  SKIP: Script not found\n")
            results.append((name, "SKIPPED", 0))
            continue

        start = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                capture_output=True, text=True,
                cwd=examples_dir, timeout=120
            )
            duration = time.time() - start
            if proc.returncode == 0:
                print(f"  OK ({duration:.1f}s)")
                results.append((name, "OK", duration))
            else:
                print(f"  FAIL ({duration:.1f}s)")
                if proc.stderr:
                    for line in proc.stderr.strip().split('\n')[-3:]:
                        print(f"    {line}")
                results.append((name, "FAIL", duration))
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT (>120s)")
            results.append((name, "TIMEOUT", 120))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((name, "ERROR", 0))
        print()

    # Summary
    total_duration = time.time() - total_start
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    passed = sum(1 for _, s, _ in results if s == "OK")
    for name, status, duration in results:
        print(f"  {status:8s}  {name:25s}  {duration:5.1f}s")
    print(f"\n  {passed}/{len(results)} examples passed")
    print(f"  Total time: {total_duration:.1f}s")


if __name__ == "__main__":
    main()
