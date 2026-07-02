#!/usr/bin/env python3
"""Helper script to split test into n buckets."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from math import ceil
import os
from pathlib import Path
import subprocess
import sys
from typing import Final

# tests/components has ~1000 sub-directories, which makes it the natural
# place to subdivide to keep each pytest invocation roughly equal in size.
_FAN_OUT_DIRS: Final = frozenset({"components"})


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

    def split_tests(self, test_folder: TestFolder) -> None:
        """Split tests into buckets."""
        digits = len(str(test_folder.total_tests))
        sorted_tests = sorted(
            test_folder.get_all_flatten(), reverse=True, key=lambda x: x.total_tests
        )
        for tests in sorted_tests:
            if tests.added_to_bucket:
                # Already added to bucket
                continue

            print(f"{tests.total_tests:>{digits}} tests in {tests.path}")
            smallest_bucket = min(self._buckets, key=lambda x: x.total_tests)
            is_file = isinstance(tests, TestFile)
            if (
                smallest_bucket.total_tests + tests.total_tests < self._tests_per_bucket
            ) or is_file:
                smallest_bucket.add(tests)
                # Ensure all files from the same folder are in the same bucket
                # to ensure that syrupy correctly identifies unused snapshots
                if is_file:
                    for other_test in tests.parent.children.values():
                        if other_test is tests or isinstance(other_test, TestFolder):
                            continue
                        print(
                            f"{other_test.total_tests:>{digits}}"
                            f" tests in {other_test.path}"
                            " (same bucket)"
                        )
                        smallest_bucket.add(other_test)

        # verify that all tests are added to a bucket
        if not test_folder.added_to_bucket:
            raise ValueError("Not all tests are added to a bucket")

    def create_ouput_file(self) -> None:
        """Create output file."""
        with Path("pytest_buckets.txt").open("w") as file:
            for idx, bucket in enumerate(self._buckets):
                print(f"Bucket {idx + 1} has {bucket.total_tests} tests")
                file.write(bucket.get_paths_line())


@dataclass
class TestFile:
    """Class represents a single test file and the number of tests it has."""

    total_tests: int
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


def _collect_batch(paths: list[Path]) -> tuple[str, str, int]:
    """Run pytest --collect-only on a batch of paths."""
    result = subprocess.run(
        ["pytest", "--collect-only", "-qq", "-p", "no:warnings", *map(str, paths)],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout, result.stderr, result.returncode


def _iter_eligible_children(path: Path) -> list[Path]:
    """Return immediate children of ``path`` that pytest should collect.

    Filters out hidden/dunder entries, non-``test_*.py`` files (so helper
    modules like ``conftest.py`` and ``common.py`` are not passed as
    explicit collection targets), and pycache-style directories.
    """
    children: list[Path] = []
    for entry in sorted(path.iterdir()):
        if entry.name.startswith((".", "_")):
            continue
        if entry.is_dir() or (entry.suffix == ".py" and entry.name.startswith("test_")):
            children.append(entry)
    return children


def _enumerate_batch_paths(path: Path) -> list[Path]:
    """Return the child paths to run pytest --collect-only over.

    Files are returned as-is.  Directories are expanded one level deep, with
    a second level of expansion for entries named in ``_FAN_OUT_DIRS`` so the
    enormous ``tests/components`` tree fans out into per-integration paths.
    """
    if path.is_file():
        return [path]

    paths: list[Path] = []
    for entry in _iter_eligible_children(path):
        if entry.is_dir() and entry.name in _FAN_OUT_DIRS:
            paths.extend(_iter_eligible_children(entry))
        else:
            paths.append(entry)
    return paths


def collect_tests(path: Path) -> TestFolder:
    """Collect all tests."""
    batch_paths = _enumerate_batch_paths(path)
    if not batch_paths:
        print(f"No eligible test paths found under {path}")
        sys.exit(1)
    workers = min(len(batch_paths), os.cpu_count() or 1) or 1
    # Round-robin chunking keeps batches roughly balanced when path
    # ordering correlates with test size.
    batches = [batch_paths[i::workers] for i in range(workers)]

    if workers == 1:
        results = [_collect_batch(batches[0])]
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(_collect_batch, batches))

    folder = TestFolder(path)
    for stdout, stderr, returncode in results:
        if returncode != 0:
            print("Failed to collect tests:")
            print(stderr)
            print(stdout)
            sys.exit(1)
        for line in stdout.splitlines():
            if not line.strip():
                continue
            file_path, _, total_tests = line.partition(": ")
            if not file_path or not total_tests:
                print(f"Unexpected line: {line}")
                sys.exit(1)

            file = TestFile(int(total_tests), Path(file_path))
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
    tests_per_bucket = ceil(tests.total_tests / arguments.bucket_count)

    bucket_holder = BucketHolder(tests_per_bucket, arguments.bucket_count)
    print("Splitting tests...")
    bucket_holder.split_tests(tests)

    print(f"Total tests: {tests.total_tests}")
    print(f"Estimated tests per bucket: {tests_per_bucket}")

    bucket_holder.create_ouput_file()


if __name__ == "__main__":
    main()
