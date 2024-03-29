#!/usr/bin/env python3
"""Remove lines from .coveragerc if they are >THRESHOLD% coverage.

Runs the full test suite and works out if any lines in .coveragerc
don't need to be there.
"""

import fileinput
import json
import os

import pytest

COVERAGERC = ".coveragerc"
THRESHOLD = 97.0
TEMP_JSON = "build/_temp_coverage.json"


def replace_all(file: str, before: str, after: str):
    """Replace all instances of string in file."""
    for line in fileinput.input(file, inplace=1):
        print(line.replace(before, after), end="")


def main():
    """Run the script."""

    if os.path.exists(TEMP_JSON):
        os.remove(TEMP_JSON)

    try:
        # Turn off all .coveragerc ignoring
        replace_all(COVERAGERC, "omit =", "omit_disabled =")

        # Run tests in parallel for speed
        pytest.main(
            [
                "-qq",
                "--timeout=9",
                "--durations=10",
                "--dist=loadfile",
                "--cov=homeassistant.components",
                "--cov-report",
                f"json:{TEMP_JSON}",
                "tests/components/",
            ]
        )

        # parse the json results file
        with open(TEMP_JSON, encoding="UTF-8") as infile:
            data = json.load(infile)

        # make a list of >THRESHOLD% passing files
        out_list = []
        for filename, file_data in data["files"].items():
            percent = file_data["summary"]["percent_covered"]
            if percent > THRESHOLD:
                out_list.append(filename)

        # remove those files from .coveragerc
        print(f">{THRESHOLD}% covered files:")
        for filename in out_list:
            print(filename)
            replace_all(COVERAGERC, f"    {filename}\n", "")

    finally:
        # Turn .coveragerc ignoring back on
        replace_all(COVERAGERC, "omit_disabled =", "omit =")


if __name__ == "__main__":
    main()
