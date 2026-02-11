"""
Report Generator

Aggregates stress test results and generates summary reports.
Locust already produces HTML and CSV reports; this module adds
a consolidated JSON summary across multiple test runs.
"""

import csv
import json
import os
from datetime import datetime
from typing import Any


def generate_summary_report(
    results: list[dict[str, Any]],
    output_dir: str = "reports",
) -> str:
    """Generate a consolidated summary report from multiple test runs.

    Args:
        results: List of result dicts from StressTestEngine.run().
        output_dir: Directory to write the summary.

    Returns:
        Path to the generated summary JSON file.
    """
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = {
        "generated_at": timestamp,
        "total_tests": len(results),
        "passed": sum(1 for r in results if r.get("return_code") == 0),
        "failed": sum(1 for r in results if r.get("return_code") != 0),
        "tests": [],
    }

    for result in results:
        test_entry = {
            "name": result.get("test_name"),
            "timestamp": result.get("timestamp"),
            "status": "PASS" if result.get("return_code") == 0 else "FAIL",
            "html_report": result.get("html_report"),
            "csv_prefix": result.get("csv_prefix"),
        }

        # Extract key metrics from stats if available
        stats = result.get("stats", [])
        if stats:
            aggregated_row = next(
                (s for s in stats if s.get("Name") == "Aggregated"), None
            )
            if aggregated_row:
                test_entry["metrics"] = {
                    "total_requests": aggregated_row.get("Request Count", "N/A"),
                    "failure_count": aggregated_row.get("Failure Count", "N/A"),
                    "avg_response_time_ms": aggregated_row.get(
                        "Average Response Time", "N/A"
                    ),
                    "median_response_time_ms": aggregated_row.get(
                        "Median Response Time", "N/A"
                    ),
                    "p95_response_time_ms": aggregated_row.get(
                        "95%", "N/A"
                    ),
                    "p99_response_time_ms": aggregated_row.get(
                        "99%", "N/A"
                    ),
                    "requests_per_sec": aggregated_row.get(
                        "Requests/s", "N/A"
                    ),
                }

        summary["tests"].append(test_entry)

    output_path = os.path.join(output_dir, f"summary_{timestamp}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"[Report] Summary report generated: {output_path}")
    return output_path


def print_results_table(results: list[dict[str, Any]]) -> None:
    """Print a formatted results table to stdout.

    Args:
        results: List of result dicts from StressTestEngine.run().
    """
    header = f"{'Test Name':<40} {'Status':<8} {'Requests':<12} {'Avg(ms)':<10} {'P95(ms)':<10} {'RPS':<10}"
    print("\n" + "=" * len(header))
    print(header)
    print("=" * len(header))

    for result in results:
        name = result.get("test_name", "Unknown")[:39]
        status = "PASS" if result.get("return_code") == 0 else "FAIL"

        stats = result.get("stats", [])
        agg = next((s for s in stats if s.get("Name") == "Aggregated"), {})

        requests = agg.get("Request Count", "-")
        avg_time = agg.get("Average Response Time", "-")
        p95_time = agg.get("95%", "-")
        rps = agg.get("Requests/s", "-")

        print(f"{name:<40} {status:<8} {requests:<12} {avg_time:<10} {p95_time:<10} {rps:<10}")

    print("=" * len(header) + "\n")
