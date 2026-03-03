#!/usr/bin/env python3
"""Helper script to split test into n buckets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
from statistics import fmean
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
        self.total_duration = 0.0
        self._paths: list[str] = []

    def add(self, part: TestFolder | TestFile) -> None:
        """Add tests to bucket."""
        part.add_to_bucket()
        self.total_tests += part.total_tests
        self.total_duration += part.total_duration
        self._paths.append(str(part.path))

    def get_paths_line(self) -> str:
        """Return paths."""
        return " ".join(self._paths) + "\n"


class BucketHolder:
    """Class to hold buckets."""

    def __init__(self, duration_per_bucket: float, bucket_count: int) -> None:
        """Initialize bucket holder."""
        self._duration_per_bucket = duration_per_bucket
        self._bucket_count = bucket_count
        self._buckets: list[Bucket] = [Bucket() for _ in range(bucket_count)]

    def split_tests(self, test_folder: TestFolder) -> None:
        """Split tests into buckets."""
        digits = len(str(test_folder.total_tests))
        sorted_tests = sorted(
            test_folder.get_all_flatten(),
            reverse=True,
            key=lambda test: (test.total_duration, test.total_tests),
        )
        for tests in sorted_tests:
            if tests.added_to_bucket:
                # Already added to bucket
                continue

            print(
                f"{tests.total_tests:>{digits}} tests in {tests.path} "
                f"(~{tests.total_duration:.2f}s)"
            )
            smallest_bucket = min(
                self._buckets, key=lambda bucket: bucket.total_duration
            )
            is_file = isinstance(tests, TestFile)
            if (
                smallest_bucket.total_duration + tests.total_duration
                < self._duration_per_bucket
            ) or is_file:
                smallest_bucket.add(tests)
                # Ensure all files from the same folder are in the same bucket
                # to ensure that syrupy correctly identifies unused snapshots
                if is_file:
                    for other_test in tests.parent.children.values():
                        if other_test is tests or isinstance(other_test, TestFolder):
                            continue
                        print(
                            f"{other_test.total_tests:>{digits}} tests in "
                            f"{other_test.path} (same bucket, "
                            f"~{other_test.total_duration:.2f}s)"
                        )
                        smallest_bucket.add(other_test)

        # verify that all tests are added to a bucket
        if not test_folder.added_to_bucket:
            raise ValueError("Not all tests are added to a bucket")

    def create_ouput_file(self) -> None:
        """Create output file."""
        with Path("pytest_buckets.txt").open("w") as file:
            for idx, bucket in enumerate(self._buckets):
                print(
                    f"Bucket {idx + 1} has {bucket.total_tests} tests "
                    f"(~{bucket.total_duration:.2f}s)"
                )
                file.write(bucket.get_paths_line())


@dataclass
class TestFile:
    """Class represents a single test file and the number of tests it has."""

    total_tests: int
    total_duration: float
    path: Path
    added_to_bucket: bool = field(default=False, init=False)
    parent: TestFolder | None = field(default=None, init=False)

    def add_to_bucket(self) -> None:
        """Add test file to bucket."""
        if self.added_to_bucket:
            raise ValueError("Already added to bucket")
        self.added_to_bucket = True

    def __gt__(self, other: TestFile) -> bool:
        """Return if greater than."""
        return self.total_duration > other.total_duration


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
    def total_duration(self) -> float:
        """Return total estimated duration in seconds."""
        return sum(test.total_duration for test in self.children.values())

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
        file.parent = self
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

        file = TestFile(int(total_tests), 0.0, Path(file_path))
        folder.add_test_file(file)

    return folder


def load_test_durations(path: Path | None) -> dict[str, float]:
    """Load known test durations keyed by file path."""
    if path is None or not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        raw_data = json.load(file)

    if not isinstance(raw_data, dict):
        raise TypeError("Durations file should contain a JSON object")

    durations: dict[str, float] = {}
    for file_path, duration in raw_data.items():
        if not isinstance(file_path, str) or not isinstance(duration, int | float):
            continue
        if duration <= 0:
            continue
        durations[file_path] = float(duration)

    return durations


def assign_estimated_durations(
    tests: TestFolder, known_durations: dict[str, float]
) -> tuple[float, int, int]:
    """Assign estimated durations to all test files.

    Files with known timings use those values. New files (without timings)
    receive an estimate based on average seconds per collected test.
    """
    all_files = [file for file in tests.get_all_flatten() if isinstance(file, TestFile)]

    known_seconds_per_test: list[float] = []
    files_without_durations = []
    for test_file in all_files:
        if test_file.total_tests <= 0:
            continue
        duration = known_durations.get(str(test_file.path))
        if duration is None:
            files_without_durations.append(test_file)
            continue
        known_seconds_per_test.append(duration / test_file.total_tests)
        test_file.total_duration = duration

    default_seconds_per_test = (
        fmean(known_seconds_per_test) if known_seconds_per_test else 0.1
    )

    for test_file in files_without_durations:
        test_file.total_duration = test_file.total_tests * default_seconds_per_test

    return default_seconds_per_test, len(files_without_durations), len(all_files)


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
    parser.add_argument(
        "--durations-file",
        help="JSON file with per-test-file durations in seconds",
        type=Path,
    )

    arguments = parser.parse_args()

    print("Collecting tests...")
    tests = collect_tests(arguments.path)
    known_durations = load_test_durations(arguments.durations_file)
    default_seconds_per_test, files_missing_durations, total_files = (
        assign_estimated_durations(tests, known_durations)
    )

    duration_per_bucket = tests.total_duration / arguments.bucket_count

    bucket_holder = BucketHolder(duration_per_bucket, arguments.bucket_count)
    print("Splitting tests...")
    bucket_holder.split_tests(tests)

    print(f"Total tests: {tests.total_tests}")
    print(f"Files missing durations: {files_missing_durations}")
    print(f"Total files: {total_files}")
    print(f"Fallback seconds per test: {default_seconds_per_test:.4f}")
    print(f"Estimated total duration: {tests.total_duration:.2f}s")
    print(f"Estimated duration per bucket: {duration_per_bucket:.2f}s")

    bucket_holder.create_ouput_file()


if __name__ == "__main__":
    main()
