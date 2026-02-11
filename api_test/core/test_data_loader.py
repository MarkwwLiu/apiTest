"""
Test Data Loader

Loads test data from test_data/ directory.
Data is completely decoupled from API definitions.

Supported formats: YAML, JSON, CSV
"""

import csv
import itertools
import json
import os
import random
from typing import Any, Iterator

import yaml


class DataLoader:
    """Loads and serves test data for API tests."""

    def __init__(self, data_dir: str = "test_data"):
        self.data_dir = data_dir
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def load(self, filename: str) -> list[dict[str, Any]]:
        """Load test data from a file (cached)."""
        if filename in self._cache:
            return self._cache[filename]

        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Test data file not found: {filepath}")

        data = self._read_file(filepath)
        self._cache[filename] = data
        return data

    def get_random(self, filename: str) -> dict[str, Any]:
        """Get a random record from a data file."""
        return random.choice(self.load(filename))

    def get_cycle(self, filename: str) -> Iterator[dict[str, Any]]:
        """Get an infinite cycling iterator over records."""
        return itertools.cycle(self.load(filename))

    def get_by_index(self, filename: str, index: int) -> dict[str, Any]:
        """Get a specific record by index (wraps around)."""
        data = self.load(filename)
        return data[index % len(data)]

    def _read_file(self, filepath: str) -> list[dict[str, Any]]:
        if filepath.endswith((".yaml", ".yml")):
            return self._read_yaml(filepath)
        elif filepath.endswith(".json"):
            return self._read_json(filepath)
        elif filepath.endswith(".csv"):
            return self._read_csv(filepath)
        else:
            raise ValueError(f"Unsupported data format: {filepath}")

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
