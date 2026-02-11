"""
Stress Test Engine

Wraps Locust to provide programmatic execution of stress tests.
Supports running tests from generated locustfiles or directly
from StressTestConfig objects.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any

from .api_parser import StressTestConfig


class StressTestEngine:
    """Engine that orchestrates stress test execution via Locust."""

    def __init__(self, report_dir: str = "reports"):
        self.report_dir = report_dir
        os.makedirs(report_dir, exist_ok=True)

    def run(
        self,
        locustfile: str,
        config: StressTestConfig,
        headless: bool = True,
        extra_args: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run a stress test using the generated locustfile.

        Args:
            locustfile: Path to the generated Locust test file.
            config: The stress test configuration.
            headless: If True, run without web UI.
            extra_args: Additional command-line arguments for Locust.

        Returns:
            Dict with test results summary and report paths.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_name = config.name.replace(" ", "_").lower()
        csv_prefix = os.path.join(self.report_dir, f"{test_name}_{timestamp}")
        html_report = os.path.join(
            self.report_dir, f"{test_name}_{timestamp}.html"
        )

        cmd = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            locustfile,
            "--host",
            config.base_url,
            "--users",
            str(config.users),
            "--spawn-rate",
            str(config.spawn_rate),
            "--run-time",
            config.run_time,
            "--csv",
            csv_prefix,
            "--html",
            html_report,
        ]

        if headless:
            cmd.append("--headless")

        if extra_args:
            cmd.extend(extra_args)

        print(f"[Engine] Running stress test: {config.name}")
        print(f"[Engine] Command: {' '.join(cmd)}")
        print(f"[Engine] Users: {config.users}, Spawn Rate: {config.spawn_rate}, Duration: {config.run_time}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )

        output = {
            "test_name": config.name,
            "timestamp": timestamp,
            "return_code": result.returncode,
            "csv_prefix": csv_prefix,
            "html_report": html_report,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

        # Try to parse stats from CSV
        stats_file = f"{csv_prefix}_stats.csv"
        if os.path.exists(stats_file):
            output["stats"] = self._parse_stats_csv(stats_file)

        summary_path = os.path.join(
            self.report_dir, f"{test_name}_{timestamp}_summary.json"
        )
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v for k, v in output.items() if k not in ("stdout", "stderr")},
                f,
                indent=2,
            )
        output["summary_file"] = summary_path

        if result.returncode == 0:
            print(f"[Engine] Test completed successfully. Report: {html_report}")
        else:
            print(f"[Engine] Test finished with return code: {result.returncode}")
            if result.stderr:
                print(f"[Engine] Stderr: {result.stderr[-500:]}")

        return output

    def run_multiple(
        self,
        test_configs: list[tuple[str, StressTestConfig]],
        headless: bool = True,
    ) -> list[dict[str, Any]]:
        """Run multiple stress tests sequentially.

        Args:
            test_configs: List of (locustfile_path, config) tuples.
            headless: If True, run without web UI.

        Returns:
            List of result dicts from each test run.
        """
        results = []
        for locustfile, config in test_configs:
            result = self.run(locustfile, config, headless=headless)
            results.append(result)
        return results

    def _parse_stats_csv(self, csv_path: str) -> list[dict[str, str]]:
        """Parse Locust stats CSV into list of dicts."""
        import csv

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
