#!/usr/bin/env python3
"""
API Test Runner - Main CLI Entry Point

Usage:
    # Generate and run all API tests:
    python run_tests.py

    # Generate test files only (don't execute):
    python run_tests.py --generate-only

    # Run a specific API definition file:
    python run_tests.py --api-file api_definitions/example_http.yaml

    # Run with HTML report:
    python run_tests.py --html

    # Run with verbose output:
    python run_tests.py -v

    # Run only tests matching a keyword:
    python run_tests.py -k "list_posts"
"""

import argparse
import subprocess
import sys

from api_test.core.api_parser import parse_api_directory, parse_api_file
from api_test.generators.pytest_generator import generate_all, generate_tests


def main():
    parser = argparse.ArgumentParser(
        description="API Test Framework - Auto-generate and run API tests"
    )
    parser.add_argument(
        "--api-dir",
        default="api_definitions",
        help="Directory containing API definition files (default: api_definitions/)",
    )
    parser.add_argument(
        "--api-file",
        help="Test a specific API definition file",
    )
    parser.add_argument(
        "--output-dir",
        default="generated_tests",
        help="Directory for generated test files (default: generated_tests/)",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Only generate test files, don't execute",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report in reports/",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose pytest output",
    )
    parser.add_argument(
        "-k",
        help="Only run tests matching this keyword expression",
    )

    args = parser.parse_args()

    # 1. Parse API definitions
    print("[Runner] Loading API definitions...")
    if args.api_file:
        configs = [parse_api_file(args.api_file)]
    else:
        configs = parse_api_directory(args.api_dir)

    if not configs:
        print("[Runner] No API definition files found.")
        sys.exit(1)

    for cfg in configs:
        http_count = len(cfg.http_endpoints)
        wss_count = len(cfg.wss_endpoints)
        scenario_count = len(cfg.scenarios)
        print(f"  - {cfg.name}: {http_count} HTTP, {wss_count} WSS, {scenario_count} scenarios")

    # 2. Generate test files
    print(f"\n[Runner] Generating pytest test files -> {args.output_dir}/")
    generated = generate_all(configs, args.output_dir)
    print(f"[Runner] Generated {len(generated)} test file(s)")

    if args.generate_only:
        print("\n[Runner] --generate-only specified, skipping execution")
        for f in generated:
            print(f"  {f}")
        return

    # 3. Run pytest
    print("\n[Runner] Running tests...")
    cmd = [sys.executable, "-m", "pytest", args.output_dir]

    if args.verbose:
        cmd.append("-v")

    if args.k:
        cmd.extend(["-k", args.k])

    if args.html:
        cmd.extend(["--html=reports/report.html", "--self-contained-html"])

    cmd.append("--tb=short")

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
