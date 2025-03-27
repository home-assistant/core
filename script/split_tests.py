#!/usr/bin/env python3
"""Helper script to split test into n buckets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast

from homeassistant.util.json import load_json_object


class Bucket:
    """Class to hold bucket."""

    def __init__(
        self,
    ):
        """Initialize bucket."""
        self.approx_execution_time = 0.0
        self.not_measured_files = 0
        self._paths: list[str] = []

    def add(self, part: TestFolder | TestFile) -> None:
        """Add tests to bucket."""
        part.add_to_bucket()
        self.approx_execution_time += part.approx_execution_time
        self.not_measured_files += part.not_measured_files
        self._paths.append(str(part.path))

    def get_paths_line(self) -> str:
        """Return paths."""
        return " ".join(self._paths) + "\n"


class BucketHolder:
    """Class to hold buckets."""

    def __init__(self, bucket_count: int) -> None:
        """Initialize bucket holder."""
        self._bucket_count = bucket_count
        self._buckets: list[Bucket] = [Bucket() for _ in range(bucket_count)]

    def split_tests(self, test_folder: TestFolder) -> None:
        """Split tests into buckets."""
        avg_execution_time = test_folder.approx_execution_time / self._bucket_count
        avg_not_measured_files = test_folder.not_measured_files / self._bucket_count
        digits = len(str(round(test_folder.approx_execution_time, 0)))
        sorted_tests = sorted(
            test_folder.get_all_flatten(),
            key=lambda x: (
                -x.approx_execution_time,
                -x.count_children() if isinstance(x, TestFolder) else 0,
                x.not_measured_files,
            ),
        )
        bucket_sort_keys = (
            lambda x: (x.not_measured_files, x.approx_execution_time),
            lambda x: (x.approx_execution_time, x.not_measured_files),
        )
        for tests in sorted_tests:
            if tests.added_to_bucket:
                # Already added to bucket
                continue

            print(
                f"~{round(tests.approx_execution_time, 2):>{digits}}s execution time for {tests.path}"
            )
            is_file = isinstance(tests, TestFile)

            for sort_key in bucket_sort_keys:
                smallest_bucket = min(self._buckets, key=sort_key)

                if (
                    (
                        smallest_bucket.approx_execution_time
                        + tests.approx_execution_time
                    )
                    < avg_execution_time
                    and (smallest_bucket.not_measured_files + tests.not_measured_files)
                    < avg_not_measured_files
                ) or is_file:
                    smallest_bucket.add(tests)
                    # Ensure all files from the same folder are in the same bucket
                    # to ensure that syrupy correctly identifies unused snapshots
                    if is_file:
                        for other_test in tests.parent.children.values():
                            if other_test is tests or isinstance(
                                other_test, TestFolder
                            ):
                                continue
                            print(
                                f"Adding {other_test.path} tests to same bucket due syrupy"
                            )
                            smallest_bucket.add(other_test)
                    break

        # verify that all tests are added to a bucket
        if not test_folder.added_to_bucket:
            raise ValueError("Not all tests are added to a bucket")

    def create_ouput_file(self) -> None:
        """Create output file."""
        with Path("pytest_buckets.txt").open("w") as file:
            for idx, bucket in enumerate(self._buckets):
                print(
                    f"Bucket {idx + 1} execution time should be ~{bucket.approx_execution_time}s"
                    f" with {bucket.not_measured_files} not measured files"
                )
                file.write(bucket.get_paths_line())


@dataclass
class TestFile:
    """Class represents a single test file and the number of tests it has."""

    path: Path
    parent: TestFolder
    # 0 means not measured
    approx_execution_time: float = 0.0
    added_to_bucket: bool = field(default=False, init=False)

    def add_to_bucket(self) -> None:
        """Add test file to bucket."""
        if self.added_to_bucket:
            raise ValueError("Already added to bucket")
        self.added_to_bucket = True

    @property
    def not_measured_files(self) -> int:
        """Return files not measured."""
        return 1 if self.approx_execution_time == 0 else 0

    def __gt__(self, other: TestFile) -> bool:
        """Return if greater than."""
        return self.approx_execution_time > other.approx_execution_time


class TestFolder:
    """Class to hold a folder with test files and folders."""

    def __init__(self, path: Path) -> None:
        """Initialize test folder."""
        self.path: Final = path
        self.children: dict[Path, TestFolder | TestFile] = {}

    @property
    def approx_execution_time(self) -> float:
        """Return approximate execution time."""
        return sum([test.approx_execution_time for test in self.children.values()])

    @property
    def not_measured_files(self) -> int:
        """Return files not measured."""
        return sum([test.not_measured_files for test in self.children.values()])

    @property
    def added_to_bucket(self) -> bool:
        """Return if added to bucket."""
        return all(test.added_to_bucket for test in self.children.values())

    def count_children(self) -> int:
        """Return the number of children."""
        return len(self.children) + sum(
            child.count_children()
            for child in self.children.values()
            if isinstance(child, TestFolder)
        )

    def add_to_bucket(self) -> None:
        """Add test file to bucket."""
        if self.added_to_bucket:
            raise ValueError("Already added to bucket")
        for child in self.children.values():
            child.add_to_bucket()

    def __repr__(self) -> str:
        """Return representation."""
        return f"TestFolder(approx_execution_time={self.approx_execution_time}, children={len(self.children)})"

    def add_test_file(
        self, path: Path, execution_time: float, skip_file_if_present: bool
    ) -> None:
        """Add test file to folder."""
        self._add_test_file(TestFile(path, self, execution_time), skip_file_if_present)

    def _add_test_file(self, file: TestFile, skip_file_if_present: bool) -> None:
        """Add test file to folder."""
        path = file.path
        file.parent = self
        relative_path = path.relative_to(self.path)
        if not relative_path.parts:
            raise ValueError("Path is not a child of this folder")

        if len(relative_path.parts) == 1:
            if path in self.children:
                if skip_file_if_present:
                    return
                raise ValueError(f"File already exists: {path}")
            self.children[path] = file
            return

        child_path = self.path / relative_path.parts[0]
        if (child := self.children.get(child_path)) is None:
            self.children[child_path] = child = TestFolder(child_path)
        elif not isinstance(child, TestFolder):
            raise ValueError("Child is not a folder")
        child._add_test_file(file, skip_file_if_present)

    def get_all_flatten(self) -> list[TestFolder | TestFile]:
        """Return self and all children as flatten list."""
        result: list[TestFolder | TestFile] = [self]
        for child in self.children.values():
            if isinstance(child, TestFolder):
                result.extend(child.get_all_flatten())
            else:
                result.append(child)
        return result


def process_execution_time_file(
    execution_time_file: Path, test_folder: TestFolder
) -> None:
    """Process the execution time file."""
    for file, execution_time in load_json_object(execution_time_file).items():
        test_folder.add_test_file(Path(file), cast(float, execution_time), False)


def add_missing_test_files(folder: Path, test_folder: TestFolder) -> None:
    """Scan test folder for missing files."""
    for path in folder.iterdir():
        if path.is_dir():
            add_missing_test_files(path, test_folder)
        elif path.name.startswith("test_") and path.suffix == ".py":
            test_folder.add_test_file(path, 0.0, True)


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
        "test_folder",
        help="Path to the test files to split into buckets",
        type=Path,
    )
    parser.add_argument(
        "execution_time_file",
        help="Path to the file containing the execution time of each test",
        type=Path,
    )

    arguments = parser.parse_args()

    tests = TestFolder(arguments.test_folder)

    if arguments.execution_time_file.exists():
        print(f"Using execution time file: {arguments.execution_time_file}")
        process_execution_time_file(arguments.execution_time_file, tests)

    print("Scanning test files...")
    add_missing_test_files(arguments.test_folder, tests)

    bucket_holder = BucketHolder(arguments.bucket_count)
    print("Splitting tests...")
    bucket_holder.split_tests(tests)

    bucket_holder.create_ouput_file()


if __name__ == "__main__":
    main()
