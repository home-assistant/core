#!/usr/bin/env python3
"""Helper script to split test into n buckets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from math import ceil
from pathlib import Path
import subprocess
import sys
from typing import Final


class Bucket:
    """Class to hold bucket."""

    def __init__(
        self,
    ):
        """Initialize bucket."""
        self.total_tests = 0
        self._paths: list[str] = []

    def add(self, part: TestFolder | TestFile) -> None:
        """Add tests to bucket."""
        part.add_to_bucket()
        self.total_tests += part.total_tests
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

    def _split_tests(self, tests: TestFolder | TestFile) -> None:
        """Split tests into buckets."""
        smallest_bucket = min(self._buckets, key=lambda x: x.total_tests)
        if (
            smallest_bucket.total_tests + tests.total_tests < self._tests_per_bucket
        ) or isinstance(tests, TestFile):
            smallest_bucket.add(tests)
            return

        if isinstance(tests, TestFolder):
            for test in sorted(
                tests.children.values(), reverse=True, key=lambda x: x.total_tests
            ):
                self._split_tests(test)

    def _flatten(self, tests: TestFolder) -> list[TestFolder | TestFile]:
        result: list[TestFolder | TestFile] = [tests]
        for child in tests.children.values():
            if isinstance(child, TestFolder):
                result.extend(self._flatten(child))
            else:
                result.append(child)
        return result

    def split_tests(self, test_folder: TestFolder) -> None:
        """Split tests into buckets."""
        sorted_tests = sorted(
            self._flatten(test_folder), reverse=True, key=lambda x: x.total_tests
        )
        for tests in sorted_tests:
            if tests.added_to_backet:
                # Already added to bucket
                continue

            smallest_bucket = min(self._buckets, key=lambda x: x.total_tests)
            if (
                smallest_bucket.total_tests + tests.total_tests < self._tests_per_bucket
            ) or isinstance(tests, TestFile):
                smallest_bucket.add(tests)

        # verify that all tests are added to a bucket
        if not test_folder.added_to_backet:
            raise ValueError("Not all tests are added to a bucket")

    def create_ouput_file(self) -> None:
        """Create output file."""
        with open("pytest_buckets.txt", "w") as file:
            for idx, bucket in enumerate(self._buckets):
                print(f"Bucket {idx+1} has {bucket.total_tests} tests")
                file.write(bucket.get_paths_line())


@dataclass
class TestFile:
    """Class represents a single test file and the number of tests it has."""

    total_tests: int
    path: Path
    added_to_backet: bool = field(default=False, init=False)

    def add_to_bucket(self) -> None:
        """Add test file to bucket."""
        if self.added_to_backet:
            raise ValueError("Already added to bucket")
        self.added_to_backet = True

    def __gt__(self, other: TestFile) -> bool:
        """Return if greater than."""
        return self.total_tests > other.total_tests


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
    def added_to_backet(self) -> bool:
        """Return if added to bucket."""
        return all(test.added_to_backet for test in self.children.values())

    def add_to_bucket(self) -> None:
        """Add test file to bucket."""
        if self.added_to_backet:
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


def collect_tests(path: Path) -> tuple[TestFolder, TestFile]:
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
    file_with_most_tests = TestFile(0, Path())

    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        file_path, _, total_tests = line.partition(": ")
        if not path or not total_tests:
            print(f"Unexpected line: {line}")
            sys.exit(1)

        file = TestFile(int(total_tests), Path(file_path))
        file_with_most_tests = max(file_with_most_tests, file)
        folder.add_test_file(file)

    return (folder, file_with_most_tests)


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
    (tests, file_with_most_tests) = collect_tests(arguments.path)
    print(
        f"Maximum tests in a single file are {file_with_most_tests.total_tests} tests (in {file_with_most_tests.path})"
    )
    print(f"Total tests: {tests.total_tests}")

    tests_per_bucket = ceil(tests.total_tests / arguments.bucket_count)
    print(f"Estimated tests per bucket: {tests_per_bucket}")

    bucket_holder = BucketHolder(tests_per_bucket, arguments.bucket_count)
    bucket_holder.split_tests(tests)
    bucket_holder.create_ouput_file()


if __name__ == "__main__":
    main()
