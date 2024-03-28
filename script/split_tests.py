#!/usr/bin/env python3
"""Helper script to split test into n buckets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from math import ceil
import os
import subprocess
import sys


class Bucket:
    """Class to hold bucket."""

    def __init__(
        self,
    ):
        """Initialize bucket."""
        self.tests = 0
        self._paths = []

    def add(self, part: TestFolder | TestFile):
        """Add tests to bucket."""
        self.tests += part.total_tests
        self._paths.append(part.path)

    def get_paths_line(self) -> str:
        """Return paths."""
        return " ".join(self._paths) + "\n"


class BucketHolder:
    """Class to hold buckets."""

    def __init__(self, tests_per_bucket: int, bucket_count: int) -> None:
        """Initialize bucket holder."""
        self._tests_per_bucket = tests_per_bucket
        self._bucket_count = bucket_count
        self._current_bucket = Bucket()
        self._buckets: list[Bucket] = [self._current_bucket]
        self._last_bucket = False

    def split_tests(self, tests: TestFolder | TestFile) -> None:
        """Split tests into buckets."""
        if (
            self._current_bucket.tests + tests.total_tests < self._tests_per_bucket
        ) or self._last_bucket:
            self._current_bucket.add(tests)
            return

        if isinstance(tests, TestFolder):
            for test in tests.children.values():
                self.split_tests(test)
            return

        # Create new bucket
        if len(self._buckets) == self._bucket_count:
            # Last bucket, add all tests to it
            self._last_bucket = True
        else:
            self._current_bucket = Bucket()
            self._buckets.append(self._current_bucket)

        # Add test to new bucket
        self.split_tests(tests)

    def create_ouput_file(self) -> None:
        """Create output file."""
        with open("pytest_buckets.txt", "w") as file:
            for bucket in self._buckets:
                print(f"Bucket has {bucket.tests} tests")
                file.write(bucket.get_paths_line())


@dataclass
class TestFile:
    """Class to hold number of tests."""

    path: str
    total_tests: int

    def __gt__(self, other):
        """Return if greater than."""
        return self.total_tests > other.total_tests


@dataclass
class TestFolder:
    """Class to hold test information."""

    path: str
    children: dict[str, TestFolder | TestFile] = field(default_factory=dict)

    @property
    def total_tests(self) -> int:
        """Return total tests."""
        return sum([test.total_tests for test in self.children.values()])

    def __repr__(self):
        """Return representation."""
        return f"TestFolder(total={self.total_tests}, children={len(self.children)})"


def insert_at_correct_position(
    test_holder: TestFolder, test_path: str, total_tests: int
) -> None:
    """Insert test at correct position."""
    current_path = test_holder
    for part in test_path.split("/")[1:]:
        if part.endswith(".py"):
            current_path.children[part] = TestFile(test_path, total_tests)
        else:
            current_path = current_path.children.setdefault(
                part, TestFolder(os.path.join(current_path.path, part))
            )


def collect_tests(path: str) -> tuple[TestFolder, TestFile]:
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

    folder = TestFolder(path.split("/")[0])
    insert_at_correct_position(folder, path, 0)
    max_tests_in_file = TestFile("", 0)

    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = [x.strip() for x in line.split(":")]
        if len(parts) != 2:
            print(f"Unexpected line: {line}")
            sys.exit(1)

        path = parts[0]
        total_tests = int(parts[1])
        max_tests_in_file = max(max_tests_in_file, TestFile(path, total_tests))

        insert_at_correct_position(folder, path, total_tests)

    return (folder, max_tests_in_file)


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

    arguments = parser.parse_args()

    print("Collecting tests...")
    (tests, max_tests_in_file) = collect_tests("tests")
    print(
        f"Maximum tests in a single file are {max_tests_in_file.total_tests} tests (in {max_tests_in_file.path})"
    )
    print(f"Total tests: {tests.total_tests}")

    tests_per_bucket = ceil(tests.total_tests / arguments.bucket_count)
    print(f"Estimated tests per bucket: {tests_per_bucket}")

    if max_tests_in_file.total_tests > tests_per_bucket:
        raise ValueError(
            f"There are more tests in a single file ({max_tests_in_file}) than tests per bucket ({tests_per_bucket})"
        )

    bucket_holder = BucketHolder(tests_per_bucket, arguments.bucket_count)
    bucket_holder.split_tests(tests)
    bucket_holder.create_ouput_file()


if __name__ == "__main__":
    main()
