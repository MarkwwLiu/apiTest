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

    # Run only tests with specific tags:
    python run_tests.py --tags read

    # Skip tests with specific tags:
    python run_tests.py --skip-tags write

    # Enable debug logging (see request/response details):
    python run_tests.py --debug
    # Or via env var:
    API_TEST_LOG_LEVEL=DEBUG python run_tests.py
"""

import argparse
import os
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
    parser.add_argument(
        "--tags",
        nargs="+",
        help="Only run tests with these tags (pytest markers)",
    )
    parser.add_argument(
        "--skip-tags",
        nargs="+",
        help="Skip tests with these tags (pytest markers)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging (shows request/response details)",
    )

    args = parser.parse_args()

    # Set debug logging
    if args.debug:
        os.environ["API_TEST_LOG_LEVEL"] = "DEBUG"

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
        auth_type = cfg.auth.type if cfg.auth else "none"
        retry = f"retry={cfg.retry.max_retries}" if cfg.retry else "no retry"
        print(f"  - {cfg.name}: {http_count} HTTP, {wss_count} WSS, {scenario_count} scenarios [auth={auth_type}, {retry}]")

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

    # Tag filtering: -m "read and not write"
    if args.tags or args.skip_tags:
        marker_expr_parts = []
        if args.tags:
            marker_expr_parts.append(" or ".join(args.tags))
        if args.skip_tags:
            for tag in args.skip_tags:
                marker_expr_parts.append(f"not {tag}")
        marker_expr = " and ".join(f"({p})" for p in marker_expr_parts)
        cmd.extend(["-m", marker_expr])

    if args.html:
        cmd.extend(["--html=reports/report.html", "--self-contained-html"])

    cmd.append("--tb=short")

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
