#!/usr/bin/env python3
"""Collect and merge pytest durations per test file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from defusedxml import ElementTree as ET


def _load_json(path: Path) -> dict[str, float]:
    """Load durations from a JSON file."""
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object in {path}")

    result: dict[str, float] = {}
    for file_path, duration in payload.items():
        if not isinstance(file_path, str) or not isinstance(duration, int | float):
            continue
        if duration <= 0:
            continue
        result[file_path] = float(duration)

    return result


def _load_junit(path: Path) -> dict[str, float]:
    """Load durations from a JUnit XML file."""
    tree = ET.parse(path)
    root = tree.getroot()

    result: dict[str, float] = {}
    for testcase in root.iter("testcase"):
        file_path = testcase.attrib.get("file")
        if not file_path:
            continue

        raw_duration = testcase.attrib.get("time", "0")
        try:
            duration = float(raw_duration)
        except ValueError:
            continue

        if duration <= 0:
            continue

        normalized = Path(file_path).as_posix()
        result[normalized] = result.get(normalized, 0.0) + duration

    return result


def _load_input(path: Path) -> dict[str, float]:
    """Load durations from either JSON or XML input."""
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _load_json(path)
    if suffix == ".xml":
        return _load_junit(path)
    raise ValueError(f"Unsupported file type for {path}")


def merge_durations(
    existing: dict[str, float],
    incoming: dict[str, float],
    smoothing: float,
) -> dict[str, float]:
    """Merge durations by smoothing with historical values.

    Formula: merged = old * (1 - smoothing) + new * smoothing
    """
    merged = dict(existing)

    for file_path, duration in incoming.items():
        previous = merged.get(file_path)
        if previous is None:
            merged[file_path] = duration
            continue
        merged[file_path] = (previous * (1 - smoothing)) + (duration * smoothing)

    return merged


def main() -> None:
    """Run the duration collector."""
    parser = argparse.ArgumentParser(
        description="Collect and merge test durations from JUnit XML or JSON files"
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="Input files (.xml or .json)",
    )
    parser.add_argument(
        "--existing",
        type=Path,
        help="Existing durations JSON file",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output JSON file",
    )
    parser.add_argument(
        "--smoothing",
        type=float,
        default=0.35,
        help="Weight for newly measured durations (0.0 to 1.0)",
    )

    args = parser.parse_args()

    if not 0 <= args.smoothing <= 1:
        raise ValueError("--smoothing must be between 0.0 and 1.0")

    merged: dict[str, float] = {}
    if args.existing and args.existing.exists():
        merged = _load_json(args.existing)

    incoming: dict[str, float] = {}
    for input_file in args.inputs:
        if not input_file.exists():
            continue
        for file_path, duration in _load_input(input_file).items():
            incoming[file_path] = incoming.get(file_path, 0.0) + duration

    merged = merge_durations(merged, incoming, args.smoothing)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        json.dump(dict(sorted(merged.items())), file, indent=2)
        file.write("\n")

    print(
        f"Wrote {len(merged)} file durations "
        f"(updated {len(incoming)} from current run) to {args.output}"
    )


if __name__ == "__main__":
    main()
