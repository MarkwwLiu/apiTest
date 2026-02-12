"""Unit tests for api_test.exporters.standalone_exporter module."""

import json
import os

import pytest
import yaml

from api_test.exporters.standalone_exporter import (
    _build_header,
    _build_imports,
    _clean_test_content,
    _extract_module_body,
    _find_project_root,
    _load_test_data,
    _section_banner,
    export_standalone,
)


# ── _find_project_root ────────────────────────────────────────


class TestFindProjectRoot:
    def test_finds_root(self, tmp_path):
        api_dir = tmp_path / "api_test"
        api_dir.mkdir()
        test_dir = tmp_path / "generated_tests"
        test_dir.mkdir()
        test_file = test_dir / "test_example.py"
        test_file.write_text("# test")
        root = _find_project_root(str(test_file))
        assert root == str(tmp_path)

    def test_raises_when_not_found(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("# test")
        with pytest.raises(RuntimeError, match="Cannot find project root"):
            _find_project_root(str(test_file))


# ── _section_banner ───────────────────────────────────────────


class TestSectionBanner:
    def test_format(self):
        banner = _section_banner("Title", "source.py")
        assert "Title" in banner
        assert "source.py" in banner
        assert "=" in banner


# ── _build_header ─────────────────────────────────────────────


class TestBuildHeader:
    def test_contains_filename(self):
        header = _build_header("/path/to/test_example.py")
        assert "test_example.py" in header
        assert "Standalone" in header
        assert "pytest" in header

    def test_standalone_name(self):
        header = _build_header("/path/test_foo.py")
        assert "test_foo_standalone.py" in header


# ── _build_imports ────────────────────────────────────────────


class TestBuildImports:
    def test_http_only(self):
        imports = _build_imports(needs_http=True, needs_wss=False)
        assert "import requests" in imports
        assert "import websocket" not in imports

    def test_wss_only(self):
        imports = _build_imports(needs_http=False, needs_wss=True)
        assert "import websocket" in imports
        assert "import requests" not in imports

    def test_both(self):
        imports = _build_imports(needs_http=True, needs_wss=True)
        assert "import requests" in imports
        assert "import websocket" in imports

    def test_neither(self):
        imports = _build_imports(needs_http=False, needs_wss=False)
        assert "import requests" not in imports
        assert "import websocket" not in imports

    def test_common_imports(self):
        imports = _build_imports(True, False)
        assert "import json" in imports
        assert "import pytest" in imports
        assert "import os" in imports


# ── _extract_module_body ──────────────────────────────────────


class TestExtractModuleBody:
    def test_strips_docstring_and_imports(self):
        source = '''"""Module docstring."""

import os
import json

from foo import bar

logger = logging.getLogger(__name__)

class MyClass:
    pass
'''
        body = _extract_module_body(source)
        assert "import os" not in body
        assert "import json" not in body
        assert "from foo" not in body
        assert "Module docstring" not in body
        assert "logger" in body
        assert "class MyClass" in body

    def test_multiline_docstring(self):
        source = '''"""
Multi-line
docstring.
"""

import os

x = 1
'''
        body = _extract_module_body(source)
        assert "Multi-line" not in body
        assert "import os" not in body
        assert "x = 1" in body

    def test_single_quote_docstring(self):
        source = """'''Single quote docstring.'''

import os

y = 2
"""
        body = _extract_module_body(source)
        assert "Single quote" not in body
        assert "y = 2" in body

    def test_no_docstring(self):
        source = """import os

z = 3
"""
        body = _extract_module_body(source)
        assert "import os" not in body
        assert "z = 3" in body

    def test_multiline_single_quote_docstring(self):
        source = """'''
Multi-line
single quotes.
'''

import sys

code = True
"""
        body = _extract_module_body(source)
        assert "Multi-line" not in body
        assert "code = True" in body


# ── _load_test_data ───────────────────────────────────────────


class TestLoadTestData:
    def test_yaml_list(self, tmp_path):
        data = [{"id": 1}, {"id": 2}]
        f = tmp_path / "data.yaml"
        f.write_text(yaml.dump(data))
        result = _load_test_data(str(f))
        assert result == data

    def test_yaml_dict_with_data_key(self, tmp_path):
        data = {"data": [{"id": 1}]}
        f = tmp_path / "data.yaml"
        f.write_text(yaml.dump(data))
        result = _load_test_data(str(f))
        assert result == [{"id": 1}]

    def test_yaml_single_dict(self, tmp_path):
        data = {"id": 1}
        f = tmp_path / "data.yaml"
        f.write_text(yaml.dump(data))
        result = _load_test_data(str(f))
        assert result == [{"id": 1}]

    def test_json_list(self, tmp_path):
        data = [{"a": 1}]
        f = tmp_path / "data.json"
        f.write_text(json.dumps(data))
        result = _load_test_data(str(f))
        assert result == data

    def test_json_dict_with_data_key(self, tmp_path):
        data = {"data": [{"b": 2}]}
        f = tmp_path / "data.json"
        f.write_text(json.dumps(data))
        result = _load_test_data(str(f))
        assert result == [{"b": 2}]

    def test_unsupported_format(self, tmp_path):
        f = tmp_path / "data.xml"
        f.write_text("<data/>")
        with pytest.raises(ValueError, match="Unsupported data format"):
            _load_test_data(str(f))


# ── _clean_test_content ──────────────────────────────────────


class TestCleanTestContent:
    def test_removes_docstring(self):
        content = '"""Auto-generated."""\nimport os\n\ndef test_foo():\n    pass\n'
        cleaned = _clean_test_content(content)
        assert "Auto-generated" not in cleaned
        assert "import os" not in cleaned
        assert "def test_foo" in cleaned

    def test_removes_framework_imports(self):
        content = 'from api_test.executors.http_executor import HttpExecutor\n\ndef test_x():\n    pass\n'
        cleaned = _clean_test_content(content)
        assert "from api_test" not in cleaned
        assert "def test_x" in cleaned

    def test_removes_sys_path_insert(self):
        content = 'sys.path.insert(0, os.path.abspath(...))\n\ndef test_y():\n    pass\n'
        cleaned = _clean_test_content(content)
        assert "sys.path" not in cleaned

    def test_removes_stdlib_imports(self):
        content = 'import os\nimport sys\nimport json\nimport re\nimport pytest\nimport time\n\ndef test_z():\n    pass\n'
        cleaned = _clean_test_content(content)
        assert "import os" not in cleaned
        assert "import sys" not in cleaned
        assert "def test_z" in cleaned

    def test_inline_data_removes_loader(self):
        content = '_loader = DataLoader(data_dir="test_data")\n_test_data = _loader.load("posts.yaml")\n\ndef test():\n    pass\n'
        cleaned = _clean_test_content(content, inline_data=True)
        assert "DataLoader" not in cleaned
        assert "_loader" not in cleaned

    def test_multiline_docstring_removal(self):
        content = '"""\nMulti-line\ndocstring.\n"""\n\ndef test_a():\n    pass\n'
        cleaned = _clean_test_content(content)
        assert "Multi-line" not in cleaned
        assert "def test_a" in cleaned

    def test_no_docstring(self):
        content = 'def test_b():\n    pass\n'
        cleaned = _clean_test_content(content)
        assert "def test_b" in cleaned

    def test_leading_blank_lines_removed(self):
        content = '\n\n\ndef test_c():\n    pass\n'
        cleaned = _clean_test_content(content)
        assert cleaned.startswith("def test_c")


# ── export_standalone (integration) ───────────────────────────


class TestExportStandalone:
    @pytest.fixture
    def project(self, tmp_path):
        """Set up a minimal project structure for export testing."""
        # api_test directory structure
        api_test = tmp_path / "api_test"
        api_test.mkdir()
        (api_test / "__init__.py").write_text("")

        executors = api_test / "executors"
        executors.mkdir()
        (executors / "__init__.py").write_text("")
        (executors / "http_executor.py").write_text(
            '"""HTTP Executor."""\n\nimport requests\n\nlogger = logging.getLogger("http")\n\nclass HttpExecutor:\n    pass\n'
        )

        core = api_test / "core"
        core.mkdir()
        (core / "__init__.py").write_text("")

        # test_data
        test_data = tmp_path / "test_data"
        test_data.mkdir()
        (test_data / "posts.yaml").write_text(yaml.dump({"data": [{"id": 1}]}))

        # generated test file
        gen = tmp_path / "generated_tests"
        gen.mkdir()
        test_content = '''"""Auto-generated test."""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_test.executors.http_executor import HttpExecutor
from api_test.core.test_data_loader import DataLoader

BASE_URL = "https://api.test"
_loader = DataLoader(data_dir="test_data")
_test_data = _loader.load("posts.yaml")

def test_example(http):
    pass
'''
        test_file = gen / "test_example_http.py"
        test_file.write_text(test_content)

        return tmp_path, str(test_file)

    def test_export_creates_file(self, project):
        root, test_file = project
        output = str(root / "exports" / "standalone.py")
        result = export_standalone(test_file, output)
        assert os.path.exists(result)

    def test_export_default_path(self, project):
        root, test_file = project
        result = export_standalone(test_file)
        assert "exports" in result
        assert "standalone" in result

    def test_exported_contains_executor(self, project):
        root, test_file = project
        output = str(root / "out.py")
        export_standalone(test_file, output)
        content = open(output).read()
        assert "HttpExecutor" in content

    def test_exported_contains_test_data(self, project):
        root, test_file = project
        output = str(root / "out.py")
        export_standalone(test_file, output)
        content = open(output).read()
        assert "_test_data" in content

    def test_exported_contains_test_function(self, project):
        root, test_file = project
        output = str(root / "out.py")
        export_standalone(test_file, output)
        content = open(output).read()
        assert "def test_example" in content

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            export_standalone("/nonexistent/test.py")

    def test_exported_no_framework_imports(self, project):
        root, test_file = project
        output = str(root / "out.py")
        export_standalone(test_file, output)
        content = open(output).read()
        assert "from api_test." not in content
        assert "sys.path.insert" not in content
