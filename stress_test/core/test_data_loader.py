"""
Test Data Loader

Loads test data from the test_data/ directory. Test data is completely
decoupled from API definitions and test logic, making it easy to swap
datasets without modifying any test code.

Supported formats:
- YAML (.yaml, .yml)
- JSON (.json)
- CSV (.csv)
"""

import csv
import itertools
import json
import os
import random
from typing import Any, Iterator

import yaml


class TestDataLoader:
    """Loads and serves test data for stress tests."""

    def __init__(self, data_dir: str = "test_data"):
        self.data_dir = data_dir
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def load(self, filename: str) -> list[dict[str, Any]]:
        """Load test data from a file. Results are cached.

        Args:
            filename: Name of the data file in test_data/ directory.

        Returns:
            List of data records (each record is a dict).
        """
        if filename in self._cache:
            return self._cache[filename]

        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Test data file not found: {filepath}")

        data = self._read_file(filepath)
        self._cache[filename] = data
        return data

    def get_random(self, filename: str) -> dict[str, Any]:
        """Get a random record from the test data file."""
        data = self.load(filename)
        return random.choice(data)

    def get_cycle(self, filename: str) -> Iterator[dict[str, Any]]:
        """Get an infinite cycling iterator over test data records.

        Useful for distributing data evenly across virtual users.
        """
        data = self.load(filename)
        return itertools.cycle(data)

    def get_by_index(self, filename: str, index: int) -> dict[str, Any]:
        """Get a specific record by index (wraps around if out of range)."""
        data = self.load(filename)
        return data[index % len(data)]

    def _read_file(self, filepath: str) -> list[dict[str, Any]]:
        """Read data from file based on extension."""
        if filepath.endswith((".yaml", ".yml")):
            return self._read_yaml(filepath)
        elif filepath.endswith(".json"):
            return self._read_json(filepath)
        elif filepath.endswith(".csv"):
            return self._read_csv(filepath)
        else:
            raise ValueError(f"Unsupported data file format: {filepath}")

    def _read_yaml(self, filepath: str) -> list[dict[str, Any]]:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return [data]

    def _read_json(self, filepath: str) -> list[dict[str, Any]]:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return [data]

    def _read_csv(self, filepath: str) -> list[dict[str, Any]]:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
