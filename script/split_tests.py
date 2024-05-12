#!/usr/bin/env python3
"""Helper script to split test into n buckets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from math import ceil
from pathlib import Path
import subprocess
import sys
from typing import Final

#
# Test weights are the relative time it takes to run a test vs
# the average test. The average test is 1.
#
TEST_WEIGHTS = {
    "tests/test_circular_imports.py": 40,
    "tests/test_bootstrap.py": 2,
    "tests/components/assist_pipeline/test_websocket.py": 3,
    "tests/components/assist_pipeline/test_init.py": 3,
    "tests/components/conversation/test_default_agent.py": 5,
    "tests/components/conversation/test_init.py": 5,
    "tests/components/hue/test_light_v2.py": 3,
    "tests/components/insteon/test_api_scenes.py": 5,
    "tests/components/rainforest_raven/test_coordinator.py": 5,
    "tests/components/sensor/test_recorder_missing_stats.py": 3,
    "tests/components/sensor/test_recorder.py": 3,
    "tests/components/zha/test_discover.py": 3,
    "tests/components/zha/test_cluster_handlers.py": 2,
}


class Bucket:
    """Class to hold bucket."""

    def __init__(
        self,
    ):
        """Initialize bucket."""
        self.total_tests = 0
        self.total_weighted_tests = 0
        self._paths: list[str] = []

    def add(self, part: TestFolder | TestFile) -> None:
        """Add tests to bucket."""
        part.add_to_bucket()
        self.total_tests += part.total_tests
        self.total_weighted_tests += part.total_weighted_tests
        self._paths.append(str(part.path))

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

    def split_tests(self, test_folder: TestFolder) -> None:
        """Split tests into buckets."""
        digits = len(str(test_folder.total_weighted_tests))
        sorted_tests = sorted(
            test_folder.get_all_flatten(),
            reverse=True,
            key=lambda x: x.total_weighted_tests,
        )
        for tests in sorted_tests:
            print(f"{tests.total_weighted_tests:>{digits}} tests in {tests.path}")
            if tests.added_to_bucket:
                # Already added to bucket
                continue

            smallest_bucket = min(self._buckets, key=lambda x: x.total_weighted_tests)
            if (
                smallest_bucket.total_weighted_tests + tests.total_weighted_tests
                < self._tests_per_bucket
            ) or isinstance(tests, TestFile):
                smallest_bucket.add(tests)

        # verify that all tests are added to a bucket
        if not test_folder.added_to_bucket:
            raise ValueError("Not all tests are added to a bucket")

    def create_output_file(self) -> None:
        """Create output file."""
        with open("pytest_buckets.txt", "w") as file:
            for idx, bucket in enumerate(self._buckets):
                print(
                    f"Bucket {idx+1} has {bucket.total_tests} tests"
                    f" ({bucket.total_weighted_tests} weighted tests)"
                )
                file.write(bucket.get_paths_line())


@dataclass(slots=True)
class TestFile:
    """Class represents a single test file and the number of tests it has."""

    total_tests: int
    path: Path
    added_to_bucket: bool
    total_weighted_tests: int

    def add_to_bucket(self) -> None:
        """Add test file to bucket."""
        if self.added_to_bucket:
            raise ValueError("Already added to bucket")
        self.added_to_bucket = True

    def __gt__(self, other: TestFile) -> bool:
        """Return if greater than."""
        return self.total_weighted_tests > other.total_weighted_tests


class TestFolder:
    """Class to hold a folder with test files and folders."""

    def __init__(self, path: Path) -> None:
        """Initialize test folder."""
        self.path: Final = path
        self.children: dict[Path, TestFolder | TestFile] = {}

    @property
    def total_tests(self) -> int:
        """Return total tests."""
        return sum([test.total_tests for test in self.children.values()])

    @property
    def total_weighted_tests(self) -> int:
        """Return total weighted tests."""
        return sum([test.total_weighted_tests for test in self.children.values()])

    @property
    def added_to_bucket(self) -> bool:
        """Return if added to bucket."""
        return all(test.added_to_bucket for test in self.children.values())

    def add_to_bucket(self) -> None:
        """Add test file to bucket."""
        if self.added_to_bucket:
            raise ValueError("Already added to bucket")
        for child in self.children.values():
            child.add_to_bucket()

    def __repr__(self) -> str:
        """Return representation."""
        return (
            f"TestFolder(total_tests={self.total_tests}, children={len(self.children)})"
        )

    def add_test_file(self, file: TestFile) -> None:
        """Add test file to folder."""
        path = file.path
        relative_path = path.relative_to(self.path)
        if not relative_path.parts:
            raise ValueError("Path is not a child of this folder")

        if len(relative_path.parts) == 1:
            self.children[path] = file
            return

        child_path = self.path / relative_path.parts[0]
        if (child := self.children.get(child_path)) is None:
            self.children[child_path] = child = TestFolder(child_path)
        elif not isinstance(child, TestFolder):
            raise ValueError("Child is not a folder")
        child.add_test_file(file)

    def get_all_flatten(self) -> list[TestFolder | TestFile]:
        """Return self and all children as flatten list."""
        result: list[TestFolder | TestFile] = [self]
        for child in self.children.values():
            if isinstance(child, TestFolder):
                result.extend(child.get_all_flatten())
            else:
                result.append(child)
        return result


def collect_tests(path: Path) -> TestFolder:
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

    folder = TestFolder(path)

    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        file_path, _, total_tests = line.partition(": ")
        if not path or not total_tests:
            print(f"Unexpected line: {line}")
            sys.exit(1)

        weight = TEST_WEIGHTS.get(file_path, 1)
        total = int(total_tests)
        file = TestFile(total, Path(file_path), False, total * weight)
        folder.add_test_file(file)

    return folder


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
    total_weighted_tests = tests.total_weighted_tests
    total_tests = tests.total_tests
    tests_per_bucket = ceil(total_weighted_tests / arguments.bucket_count)

    bucket_holder = BucketHolder(tests_per_bucket, arguments.bucket_count)
    print("Splitting tests...")
    bucket_holder.split_tests(tests)

    print(f"Total tests: {total_tests}")
    print(f"Total weighted tests: {total_weighted_tests}")
    print(f"Estimated tests per bucket: {tests_per_bucket}")

    bucket_holder.create_output_file()


if __name__ == "__main__":
    main()
