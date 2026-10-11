"""Tests for the pytest_durations script."""

import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from script import pytest_durations

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest">
<testcase classname="tests.test_a" name="test_1" file="tests/test_a.py" time="1.25"/>
<testcase classname="tests.test_a" name="test_2" file="tests/test_a.py" time="0.75">
<skipped message="skip"/>
</testcase>
<testcase classname="tests.test_b" name="test_1" file="tests/test_b.py" time="3"/>
<testcase classname="tests.test_b.TestClass" name="test_2" time="1"/>
<testcase classname="tests.test_c" name="test_1" time="5"/>
</testsuite></testsuites>
"""


@pytest.fixture(autouse=True)
def chdir_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run in a tree where tests/test_a.py and tests/test_b.py exist."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").touch()
    (tmp_path / "tests" / "test_b.py").touch()
    monkeypatch.chdir(tmp_path)


def test_junit_file_durations(tmp_path: Path) -> None:
    """Times are summed per file, found by ``file`` or else by ``classname``."""
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT)
    assert pytest_durations.junit_file_durations(junit) == {
        "tests/test_a.py": 2.0,
        "tests/test_b.py": 4.0,
    }


def test_merge_durations() -> None:
    """Reports override the base, are averaged, and gone files are dropped."""
    merged = pytest_durations.merge_durations(
        [{"tests/test_a.py": 2.0}, {"tests/test_a.py": 4.0}],
        {"tests/test_a.py": 100.0, "tests/test_b.py": 5.0, "tests/gone.py": 1.0},
    )
    assert merged == {"tests/test_a.py": 3.0, "tests/test_b.py": 5.0}


def test_main(tmp_path: Path) -> None:
    """The script merges the reports over the base and writes JSON."""
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT)
    output = tmp_path / "durations.json"
    output.write_text('{"tests/test_b.py": 9, "tests/test_c.py": 1}')
    argv = ["pytest_durations", "--base", str(output), "--output", str(output)]
    with patch.object(sys, "argv", [*argv, str(junit)]):
        pytest_durations.main()
    assert json.loads(output.read_text()) == {
        "tests/test_a.py": 2.0,
        "tests/test_b.py": 4.0,
    }


def test_main_without_base_or_reports(tmp_path: Path) -> None:
    """A missing base and no reports write an empty mapping."""
    output = tmp_path / "durations.json"
    argv = ["pytest_durations", "--base", str(tmp_path / "missing.json")]
    with patch.object(sys, "argv", [*argv, "--output", str(output)]):
        pytest_durations.main()
    assert json.loads(output.read_text()) == {}
