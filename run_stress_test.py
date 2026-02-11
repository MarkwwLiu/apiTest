#!/usr/bin/env python3
"""
API Stress Test Runner - Main CLI Entry Point

Usage:
    # Generate and run all API definitions (multi mode):
    python run_stress_test.py

    # Generate tests only (don't execute):
    python run_stress_test.py --generate-only

    # Run a specific API definition file:
    python run_stress_test.py --api-file api_definitions/example_single_api.yaml

    # Specify test mode (single / multi / scenario):
    python run_stress_test.py --mode scenario

    # Run all modes for all definitions:
    python run_stress_test.py --mode all

    # Custom parameters:
    python run_stress_test.py --users 50 --spawn-rate 10 --run-time 2m

    # Launch Locust web UI (not headless):
    python run_stress_test.py --web-ui
"""

import argparse
import sys

from stress_test.core.api_parser import parse_api_directory, parse_api_file
from stress_test.core.engine import StressTestEngine
from stress_test.generators.locust_generator import generate_all, generate_locustfile
from stress_test.reports.report_generator import generate_summary_report, print_results_table


def main():
    parser = argparse.ArgumentParser(
        description="API Stress Test Framework - Auto-generate and run stress tests from API definitions"
    )
    parser.add_argument(
        "--api-dir",
        default="api_definitions",
        help="Directory containing API definition YAML/JSON files (default: api_definitions/)",
    )
    parser.add_argument(
        "--api-file",
        help="Run a specific API definition file instead of the whole directory",
    )
    parser.add_argument(
        "--mode",
        choices=["single", "multi", "scenario", "all"],
        default="multi",
        help="Test mode: single (first endpoint), multi (all endpoints), scenario (chain), all (default: multi)",
    )
    parser.add_argument(
        "--output-dir",
        default="generated_tests",
        help="Directory for generated test files (default: generated_tests/)",
    )
    parser.add_argument(
        "--report-dir",
        default="reports",
        help="Directory for test reports (default: reports/)",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Only generate test files, don't execute them",
    )
    parser.add_argument(
        "--users",
        type=int,
        help="Override number of concurrent users",
    )
    parser.add_argument(
        "--spawn-rate",
        type=int,
        help="Override user spawn rate",
    )
    parser.add_argument(
        "--run-time",
        help="Override test duration (e.g., 30s, 1m, 5m)",
    )
    parser.add_argument(
        "--web-ui",
        action="store_true",
        help="Launch Locust with web UI instead of headless mode",
    )

    args = parser.parse_args()

    # Parse API definitions
    print("[Runner] Loading API definitions...")
    if args.api_file:
        configs = [parse_api_file(args.api_file)]
    else:
        configs = parse_api_directory(args.api_dir)

    if not configs:
        print("[Runner] No API definition files found. Add YAML/JSON files to api_definitions/")
        sys.exit(1)

    print(f"[Runner] Loaded {len(configs)} API definition(s)")

    # Apply CLI overrides
    for config in configs:
        if args.users:
            config.users = args.users
        if args.spawn_rate:
            config.spawn_rate = args.spawn_rate
        if args.run_time:
            config.run_time = args.run_time

    # Determine modes to generate
    if args.mode == "all":
        modes = ["single", "multi", "scenario"]
    else:
        modes = [args.mode]

    # Generate test files
    print(f"[Runner] Generating test files (modes: {', '.join(modes)})...")
    generated_files = generate_all(configs, args.output_dir, modes)
    print(f"[Runner] Generated {len(generated_files)} test file(s)")

    if args.generate_only:
        print("[Runner] --generate-only specified, skipping execution")
        for f in generated_files:
            print(f"  - {f}")
        return

    # Run tests
    engine = StressTestEngine(report_dir=args.report_dir)
    headless = not args.web_ui

    # Build (locustfile, config) pairs
    test_pairs = []
    for config in configs:
        for mode in modes:
            test_name = config.name.replace(" ", "_").lower()
            filename = f"test_{test_name}_{mode}.py"
            filepath = f"{args.output_dir}/{filename}"
            test_pairs.append((filepath, config))

    print(f"\n[Runner] Executing {len(test_pairs)} stress test(s)...")
    results = engine.run_multiple(test_pairs, headless=headless)

    # Generate report
    print_results_table(results)
    summary_path = generate_summary_report(results, args.report_dir)
    print(f"[Runner] Done! Summary report: {summary_path}")


if __name__ == "__main__":
    main()
