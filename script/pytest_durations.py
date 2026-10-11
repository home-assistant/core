#!/usr/bin/env python3
"""Merge pytest JUnit XML reports into per-file durations for split_tests.

The output maps each test file to the seconds its tests took, which
``script/split_tests.py --durations`` uses to balance the full-run buckets.
"""

import argparse
from collections import defaultdict
from collections.abc import Iterable
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from script.split_tests import load_durations


def _classname_to_file(classname: str) -> str | None:
    """Map ``tests.a.test_b[.TestClass]`` to ``tests/a/test_b.py`` if it exists."""
    parts = classname.split(".")
    while parts:
        if (file := Path(*parts).with_suffix(".py")).is_file():
            return file.as_posix()
        parts.pop()
    return None


def junit_file_durations(junit: Path) -> dict[str, float]:
    """Return ``{test file: summed testcase seconds}`` for one JUnit report.

    The ``file`` attribute is only written with ``junit_family=legacy``;
    otherwise the file is derived from the ``classname``.
    """
    durations: dict[str, float] = defaultdict(float)
    # Reports come from this workflow's own pytest runs.
    for _, element in ET.iterparse(junit):  # noqa: S314
        if element.tag != "testcase":
            continue
        if file := element.get("file") or _classname_to_file(
            element.get("classname", "")
        ):
            durations[file] += float(element.get("time") or 0)
        element.clear()
    return durations


def merge_durations(
    reports: Iterable[dict[str, float]], base: dict[str, float] | None = None
) -> dict[str, float]:
    """Merge reports over ``base``; a file in several reports gets their mean.

    ``base`` keeps the files the reports miss (e.g. a bucket that didn't
    finish); files that no longer exist are dropped.
    """
    totals: dict[str, float] = defaultdict(float)
    seen: dict[str, int] = defaultdict(int)
    for report in reports:
        for file, seconds in report.items():
            totals[file] += seconds
            seen[file] += 1
    merged = dict(base or {})
    merged.update({file: totals[file] / seen[file] for file in totals})
    return {
        file: round(seconds, 2)
        for file, seconds in sorted(merged.items())
        if Path(file).is_file()
    }


def main() -> None:
    """Execute script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("junit", nargs="*", type=Path, help="JUnit XML reports")
    parser.add_argument(
        "--base",
        type=Path,
        help="Previous durations file whose entries are kept when not re-measured",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Durations JSON to write"
    )
    arguments = parser.parse_args()

    base = load_durations(arguments.base) if arguments.base else {}
    merged = merge_durations(
        (junit_file_durations(junit) for junit in arguments.junit), base
    )
    arguments.output.write_text(
        json.dumps(merged, indent=0, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {len(merged)} file durations from {len(arguments.junit)} reports"
        f" ({len(base)} in base)"
    )


if __name__ == "__main__":
    main()
