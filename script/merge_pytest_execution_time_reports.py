#!/usr/bin/env python3
"""Helper script to merge all pytest execution time reports into one file."""

from __future__ import annotations

import argparse
import pathlib

from homeassistant.helpers.json import save_json
from homeassistant.util.json import load_json_object


def merge_json_files(pattern: str, output_file: str) -> None:
    """Merge JSON files matching the pattern into a single JSON file."""
    # Needs to be in sync with PytestExecutionTimeReport in conftest.py
    result: dict[str, float] = {}

    for file in pathlib.Path().glob(pattern):
        print(f"Processing {file}")
        data = load_json_object(file)
        if not isinstance(data, dict):
            print(f"Skipping {file} due to invalid data format.")
            continue
        for key, value in data.items():
            if not isinstance(value, (int, float)):
                print(
                    f"Skipping {key} in {file} due to invalid value type: {type(value)}."
                )
                continue
            if key in result:
                result[key] += value
            else:
                result[key] = value

    # Write the merged data to the output file
    save_json(output_file, result)


def main() -> None:
    """Execute script."""
    parser = argparse.ArgumentParser(
        description="Merge all pytest execution time reports into one file."
    )
    parser.add_argument(
        "pattern",
        help="Glob pattern to match JSON  pytest execution time report files",
        type=str,
    )
    parser.add_argument(
        "output_file",
        help="Path to the output file",
        type=str,
        nargs="?",
        default="pytest-execution-time-report.json",
    )
    arguments = parser.parse_args()
    merge_json_files(arguments.pattern, arguments.output_file)


if __name__ == "__main__":
    main()
