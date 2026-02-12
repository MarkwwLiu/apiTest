"""
Standalone Test Exporter

Exports a generated test file as a self-contained single-file Python script.
All dependencies (executors, data loader, test data, conftest hooks) are
inlined so the script can run independently with just `pytest`.

Usage:
    python run_tests.py --export generated_tests/test_example_http_api_http.py
    python run_tests.py --export <file> --output /path/to/standalone.py
"""

import os
import re
import time
from typing import Any

import yaml


def export_standalone(test_file: str, output_path: str | None = None) -> str:
    """Export a generated test file as a self-contained standalone script.

    Reads the generated test file, detects which framework modules it uses,
    and inlines all dependency source code into a single portable .py file.

    Args:
        test_file: Path to the generated test file.
        output_path: Output file path. If None, writes to exports/<name>_standalone.py.

    Returns:
        Path to the exported standalone file.
    """
    if not os.path.exists(test_file):
        raise FileNotFoundError(f"Test file not found: {test_file}")

    project_root = _find_project_root(test_file)
    test_content = _read_file(test_file)

    # Detect which dependencies are needed
    needs_http = "from api_test.executors.http_executor import HttpExecutor" in test_content
    needs_wss = "from api_test.executors.wss_executor import WssExecutor" in test_content
    needs_data_loader = "from api_test.core.test_data_loader import DataLoader" in test_content

    # Detect test data file
    test_data_match = re.search(r'_loader\.load\(["\']([^"\']+)["\']\)', test_content)
    test_data_filename = test_data_match.group(1) if test_data_match else None

    # Build the standalone file from sections
    sections: list[str] = []

    # 1. File header with shebang and docstring
    sections.append(_build_header(test_file))

    # 2. All imports (stdlib + third-party)
    sections.append(_build_imports(needs_http, needs_wss))

    # 3. Logging setup + JSON report hooks
    sections.append(_build_conftest_inline())

    # 4. Inline executor source code
    if needs_http:
        src_path = os.path.join(project_root, "api_test", "executors", "http_executor.py")
        body = _extract_module_body(_read_file(src_path))
        body = re.sub(r'\blogger\b', '_logger_http', body)
        sections.append(
            _section_banner("HttpExecutor", "api_test/executors/http_executor.py")
            + body
        )

    if needs_wss:
        src_path = os.path.join(project_root, "api_test", "executors", "wss_executor.py")
        body = _extract_module_body(_read_file(src_path))
        body = re.sub(r'\blogger\b', '_logger_wss', body)
        sections.append(
            _section_banner("WssExecutor", "api_test/executors/wss_executor.py")
            + body
        )

    # 5. Inline test data (replace DataLoader with direct assignment)
    if test_data_filename and needs_data_loader:
        data_path = os.path.join(project_root, "test_data", test_data_filename)
        if os.path.exists(data_path):
            inline_data = _load_test_data(data_path)
            sections.append(
                _section_banner("Test Data", f"test_data/{test_data_filename}")
                + f"_test_data = {repr(inline_data)}\n"
            )

    # 6. Cleaned test code (framework imports removed)
    cleaned = _clean_test_content(test_content, inline_data=test_data_filename is not None)
    sections.append(
        _section_banner("Test Cases", os.path.basename(test_file))
        + cleaned
    )

    # Determine output path
    if output_path is None:
        export_dir = os.path.join(project_root, "exports")
        os.makedirs(export_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(test_file))[0]
        output_path = os.path.join(export_dir, f"{base_name}_standalone.py")
    else:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

    content = "\n".join(sections) + "\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


# ── Internal helpers ─────────────────────────────────────────────


def _find_project_root(test_file: str) -> str:
    """Walk up from the test file to find the project root (contains api_test/)."""
    path = os.path.abspath(os.path.dirname(test_file))
    for _ in range(10):  # max depth
        if os.path.isdir(os.path.join(path, "api_test")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    raise RuntimeError(
        f"Cannot find project root (directory containing api_test/) "
        f"starting from {test_file}"
    )


def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _section_banner(title: str, source: str) -> str:
    bar = "=" * 62
    return f"\n\n# {bar}\n# {title} (from {source})\n# {bar}\n\n"


def _build_header(test_file: str) -> str:
    basename = os.path.basename(test_file)
    standalone_name = basename.replace(".py", "_standalone.py")
    return f'''#!/usr/bin/env python3
"""
Standalone API Test Script

Exported from: {basename}
Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}

This is a self-contained test file with all dependencies inlined.
No framework installation needed - just install the pip packages below.

Run:
    pytest {standalone_name} -v
    API_TEST_LOG_LEVEL=DEBUG pytest {standalone_name} -v

Dependencies:
    pip install pytest requests websocket-client
"""'''


def _build_imports(needs_http: bool, needs_wss: bool) -> str:
    lines = [
        "",
        "# Standard library",
        "import json",
        "import logging",
        "import os",
        "import re",
        "import time",
        "from dataclasses import dataclass, field",
        "from typing import Any",
        "",
        "# Third-party",
        "import pytest",
    ]
    if needs_http:
        lines.append("import requests")
    if needs_wss:
        lines.append("import websocket")
    return "\n".join(lines)


def _build_conftest_inline() -> str:
    return '''


# ==============================================================
# Logging & JSON Report
# ==============================================================

_log_level = os.environ.get("API_TEST_LOG_LEVEL", "WARNING").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.WARNING),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

_report_results = []


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        _report_results.append({
            "test": item.nodeid,
            "outcome": report.outcome,
            "duration": round(report.duration, 3),
            "tags": [m.name for m in item.iter_markers()],
        })


def pytest_sessionfinish(session, exitstatus):
    if not _report_results:
        return
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "report.json")
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(_report_results),
        "passed": sum(1 for r in _report_results if r["outcome"] == "passed"),
        "failed": sum(1 for r in _report_results if r["outcome"] == "failed"),
        "skipped": sum(1 for r in _report_results if r["outcome"] == "skipped"),
        "results": _report_results,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)'''


def _extract_module_body(source: str) -> str:
    """Extract the body of a Python module, stripping docstring and import lines.

    Returns everything after the module docstring and import block.
    """
    lines = source.split("\n")
    result: list[str] = []
    in_docstring = False
    past_header = False
    docstring_quote: str | None = None

    for line in lines:
        stripped = line.strip()

        if not past_header:
            # Handle module docstring
            if not in_docstring:
                if stripped.startswith('"""'):
                    docstring_quote = '"""'
                    if stripped.count('"""') >= 2 and len(stripped) > 3:
                        continue  # single-line docstring
                    in_docstring = True
                    continue
                elif stripped.startswith("'''"):
                    docstring_quote = "'''"
                    if stripped.count("'''") >= 2 and len(stripped) > 3:
                        continue
                    in_docstring = True
                    continue
            else:
                if docstring_quote and docstring_quote in stripped:
                    in_docstring = False
                    docstring_quote = None
                continue

            # Skip import lines
            if stripped.startswith("import ") or stripped.startswith("from "):
                continue

            # Skip blank lines in the header
            if not stripped:
                continue

            # First real content line = body starts
            past_header = True

        result.append(line)

    return "\n".join(result)


def _load_test_data(file_path: str) -> list[dict[str, Any]]:
    """Load test data from a YAML/JSON file and return as a Python list."""
    if file_path.endswith((".yaml", ".yml")):
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    elif file_path.endswith(".json"):
        import json
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        raise ValueError(f"Unsupported data format: {file_path}")

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return [data]


def _clean_test_content(test_content: str, inline_data: bool = False) -> str:
    """Clean the generated test file content for standalone use.

    Removes:
    - Module docstring
    - import os / import sys / import json / import re / import pytest
    - sys.path.insert(...) lines
    - from api_test.* imports
    - DataLoader setup lines (when data is inlined)
    """
    lines = test_content.split("\n")
    result: list[str] = []
    in_docstring = False
    docstring_done = False

    for line in lines:
        stripped = line.strip()

        # Skip module docstring
        if not docstring_done:
            if not in_docstring:
                if stripped.startswith('"""'):
                    if stripped.count('"""') >= 2 and len(stripped) > 3:
                        docstring_done = True
                        continue
                    in_docstring = True
                    continue
                # Skip blank lines before docstring
                if not stripped:
                    continue
                # No docstring - mark done and process normally
                docstring_done = True
            else:
                if '"""' in stripped:
                    in_docstring = False
                    docstring_done = True
                continue

        # Skip standard imports (already in shared header)
        if stripped in (
            "import os", "import sys", "import json", "import re",
            "import pytest", "import time",
        ):
            continue

        # Skip sys.path.insert lines
        if "sys.path.insert" in stripped:
            continue

        # Skip framework imports
        if stripped.startswith("from api_test."):
            continue

        # Skip DataLoader setup when data is inlined
        if inline_data:
            if "_loader = DataLoader(" in stripped:
                continue
            if "_test_data = _loader.load(" in stripped:
                continue

        result.append(line)

    # Remove leading blank lines
    while result and not result[0].strip():
        result.pop(0)

    return "\n".join(result)
