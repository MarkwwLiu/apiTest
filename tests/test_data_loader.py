"""Unit tests for api_test.core.test_data_loader module."""

import csv
import json
import os

import pytest
import yaml

from api_test.core.test_data_loader import DataLoader


@pytest.fixture
def data_dir(tmp_path):
    """Create a temporary test data directory."""
    return str(tmp_path)


@pytest.fixture
def loader(data_dir):
    return DataLoader(data_dir=data_dir)


# ── YAML loading ─────────────────────────────────────────────


class TestReadYaml:
    def test_load_yaml_list(self, data_dir, loader):
        data = [{"name": "a"}, {"name": "b"}]
        path = os.path.join(data_dir, "list.yaml")
        with open(path, "w") as f:
            yaml.dump(data, f)
        result = loader.load("list.yaml")
        assert result == data

    def test_load_yaml_dict_with_data_key(self, data_dir, loader):
        data = {"data": [{"id": 1}, {"id": 2}]}
        path = os.path.join(data_dir, "dict_data.yaml")
        with open(path, "w") as f:
            yaml.dump(data, f)
        result = loader.load("dict_data.yaml")
        assert result == [{"id": 1}, {"id": 2}]

    def test_load_yaml_single_dict(self, data_dir, loader):
        data = {"name": "single", "value": 42}
        path = os.path.join(data_dir, "single.yaml")
        with open(path, "w") as f:
            yaml.dump(data, f)
        result = loader.load("single.yaml")
        assert result == [{"name": "single", "value": 42}]

    def test_load_yml_extension(self, data_dir, loader):
        data = [{"x": 1}]
        path = os.path.join(data_dir, "test.yml")
        with open(path, "w") as f:
            yaml.dump(data, f)
        result = loader.load("test.yml")
        assert result == [{"x": 1}]


# ── JSON loading ──────────────────────────────────────────────


class TestReadJson:
    def test_load_json_list(self, data_dir, loader):
        data = [{"a": 1}, {"a": 2}]
        path = os.path.join(data_dir, "list.json")
        with open(path, "w") as f:
            json.dump(data, f)
        result = loader.load("list.json")
        assert result == data

    def test_load_json_dict_with_data_key(self, data_dir, loader):
        data = {"data": [{"id": 10}]}
        path = os.path.join(data_dir, "dict.json")
        with open(path, "w") as f:
            json.dump(data, f)
        result = loader.load("dict.json")
        assert result == [{"id": 10}]

    def test_load_json_single_dict(self, data_dir, loader):
        data = {"name": "one"}
        path = os.path.join(data_dir, "one.json")
        with open(path, "w") as f:
            json.dump(data, f)
        result = loader.load("one.json")
        assert result == [{"name": "one"}]


# ── CSV loading ───────────────────────────────────────────────


class TestReadCsv:
    def test_load_csv(self, data_dir, loader):
        path = os.path.join(data_dir, "data.csv")
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "age"])
            writer.writeheader()
            writer.writerow({"name": "Alice", "age": "30"})
            writer.writerow({"name": "Bob", "age": "25"})
        result = loader.load("data.csv")
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["age"] == "25"


# ── Error handling ────────────────────────────────────────────


class TestErrors:
    def test_file_not_found(self, loader):
        with pytest.raises(FileNotFoundError, match="Test data file not found"):
            loader.load("nonexistent.yaml")

    def test_unsupported_format(self, data_dir, loader):
        path = os.path.join(data_dir, "bad.xml")
        with open(path, "w") as f:
            f.write("<data/>")
        with pytest.raises(ValueError, match="Unsupported data format"):
            loader.load("bad.xml")


# ── Caching ───────────────────────────────────────────────────


class TestCaching:
    def test_load_is_cached(self, data_dir, loader):
        data = [{"cached": True}]
        path = os.path.join(data_dir, "cached.yaml")
        with open(path, "w") as f:
            yaml.dump(data, f)
        result1 = loader.load("cached.yaml")
        result2 = loader.load("cached.yaml")
        assert result1 is result2  # same object reference = cached


# ── Access methods ────────────────────────────────────────────


class TestAccessMethods:
    @pytest.fixture(autouse=True)
    def setup_data(self, data_dir, loader):
        self.loader = loader
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        path = os.path.join(data_dir, "items.yaml")
        with open(path, "w") as f:
            yaml.dump(data, f)

    def test_get_random(self):
        record = self.loader.get_random("items.yaml")
        assert record["id"] in [1, 2, 3]

    def test_get_by_index(self):
        assert self.loader.get_by_index("items.yaml", 0)["id"] == 1
        assert self.loader.get_by_index("items.yaml", 2)["id"] == 3

    def test_get_by_index_wraps(self):
        assert self.loader.get_by_index("items.yaml", 3)["id"] == 1
        assert self.loader.get_by_index("items.yaml", 5)["id"] == 3

    def test_get_cycle(self):
        cycle = self.loader.get_cycle("items.yaml")
        results = [next(cycle) for _ in range(7)]
        assert results[0]["id"] == 1
        assert results[3]["id"] == 1  # wraps
        assert results[6]["id"] == 1  # wraps again
