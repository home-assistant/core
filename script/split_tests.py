#!/usr/bin/env python3
"""Helper script to split test into n buckets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from math import ceil
from pathlib import Path
import subprocess
import sys


class Bucket:
    """Class to hold bucket."""

    def __init__(
        self,
    ):
        """Initialize bucket."""
        self.total_tests = 0
        self._paths: list[str] = []

    def add(self, file: TestFile) -> None:
        """Add tests to bucket."""
        self.total_tests += file.total_tests
        self._paths.append(str(file.path))

    def get_paths_line(self) -> str:
        """Return paths."""
        return " ".join(self._paths) + "\n"


class BucketHolder:
    """Class to hold buckets."""

    def __init__(self, tests_per_bucket: int, bucket_count: int) -> None:
        """Initialize bucket holder."""
        self._tests_per_bucket = tests_per_bucket
        self._bucket_count = bucket_count
        self._buckets: list[Bucket] = [Bucket() for _ in range(bucket_count)]

    def _add_test(self, test: TestFile) -> None:
        """Add test to bucket."""
        smallest_bucket = min(self._buckets, key=lambda b: b.total_tests)
        smallest_bucket.add(test)

    def split_tests(self, tests: list[TestFile]) -> None:
        """Split tests into buckets."""
        for test in tests:
            self._add_test(test)

    def create_ouput_file(self) -> None:
        """Create output file."""
        with open("pytest_buckets.txt", "w") as file:
            for bucket in self._buckets:
                print(f"Bucket has {bucket.total_tests} tests")
                file.write(bucket.get_paths_line())


@dataclass
class TestFile:
    """Class represents a single test file and the number of tests it has."""

    path: Path
    total_tests: int

    def __gt__(self, other: TestFile) -> bool:
        """Return if greater than."""
        return self.total_tests > other.total_tests


def collect_tests(path: Path) -> list[TestFile]:
    """Collect all tests."""
    result = subprocess.run(
        ["pytest", "--collect-only", "-qq", "-p", "no:warnings", path],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Failed to collect tests:")
        print(result.stderr)
        print(result.stdout)
        sys.exit(1)

    files = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        file_path, _, total_tests = line.partition(": ")
        if not path or not total_tests:
            print(f"Unexpected line: {line}")
            sys.exit(1)

        files.append(TestFile(Path(file_path), int(total_tests)))

    return sorted(files, reverse=True)


def main() -> None:
    """Execute script."""
    parser = argparse.ArgumentParser(description="Split tests into n buckets.")

    def check_greater_0(value: str) -> int:
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError(
                f"{value} is an invalid. Must be greater than 0"
            )
        return ivalue

    parser.add_argument(
        "bucket_count",
        help="Number of buckets to split tests into",
        type=check_greater_0,
    )
    parser.add_argument(
        "path",
        help="Path to the test files to split into buckets",
        type=Path,
    )

    arguments = parser.parse_args()

    print("Collecting tests...")
    tests = collect_tests(arguments.path)
    file_with_most_tests = tests[0]
    print(
        f"Maximum tests in a single file are {file_with_most_tests.total_tests} tests (in {file_with_most_tests.path})"
    )
    total_tests = sum([t.total_tests for t in tests])
    print(f"Total tests: {total_tests}")

    tests_per_bucket = ceil(total_tests / arguments.bucket_count)
    print(f"Estimated tests per bucket: {tests_per_bucket}")

    if file_with_most_tests.total_tests > tests_per_bucket:
        raise ValueError(
            f"There are more tests in a single file ({file_with_most_tests}) than tests per bucket ({tests_per_bucket})"
        )

    bucket_holder = BucketHolder(tests_per_bucket, arguments.bucket_count)
    bucket_holder.split_tests(tests)
    bucket_holder.create_ouput_file()


if __name__ == "__main__":
    main()
