#!/usr/bin/env python3
"""Helper script to split test into n buckets."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
import hashlib
import json
from math import ceil
import os
from pathlib import Path
import subprocess
import sys
from typing import Final

# tests/components has ~1000 sub-directories, which makes it the natural
# place to subdivide to keep each pytest invocation roughly equal in size.
_FAN_OUT_DIRS: Final = frozenset({"components"})

# Cache file format version; bump on any incompatible schema change so old
# caches are ignored rather than misread.
_CACHE_VERSION: Final = 2


class Bucket:
    """Class to hold bucket."""

    def __init__(self) -> None:
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

    def create_output_file(self) -> None:
        """Create output file."""
        with Path("pytest_buckets.txt").open("w", encoding="utf-8") as file:
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

    Skips entries whose name starts with ``.`` or ``_`` (hidden dirs,
    ``__pycache__``, private helpers), and non-``test_*.py`` files (so
    helper modules like ``conftest.py`` and ``common.py`` are not passed
    as explicit collection targets).
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


def _hash_file(path: Path) -> str:
    """Return a short content hash for ``path``."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _walk_test_tree(root: Path) -> tuple[list[Path], list[Path]]:
    """Walk ``root`` once and return (test files, fixture files).

    Test files are the ``test_*.py`` modules that pytest will collect.
    Fixture files are every other ``.py`` under ``root`` — ``conftest.py``
    plus helper modules like ``common.py``.  Helpers go into the
    invalidation hash because they often hold the ``VALUES`` lists that
    test files import for ``@pytest.mark.parametrize``: editing one
    changes a test's collected count even though the test file itself is
    untouched.

    Uses ``os.walk`` rather than ``Path.rglob`` because it's ~2x faster on
    a 5000-file tree, and subdirectories whose names start with ``.`` or
    ``_`` are pruned instead of visited (hidden dirs, ``__pycache__``,
    private helpers).  Doing both walks in one pass keeps total tree I/O
    down.
    """
    test_files: list[Path] = []
    fixtures: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "_"))]
        base = Path(dirpath)
        for name in filenames:
            if not name.endswith(".py"):
                continue
            if name.startswith("test_"):
                test_files.append(base / name)
            else:
                fixtures.append(base / name)
    test_files.sort()
    fixtures.sort()
    return test_files, fixtures


def _find_ancestor_conftests(root: Path) -> list[Path]:
    """Return ancestor ``conftest.py`` files that pytest would still apply.

    Pytest walks up from each test file looking for conftests; when
    ``root`` is a subtree (eg ``tests/components``) the conftests above
    it (eg ``tests/conftest.py``) still affect parametrization, so they
    must contribute to the invalidation hash too.  Stops at the first
    ancestor without a ``conftest.py``.
    """
    ancestors: list[Path] = []
    current = root.resolve().parent
    while True:
        conftest = current / "conftest.py"
        if not conftest.is_file():
            break
        ancestors.append(conftest)
        if current == current.parent:
            break
        current = current.parent
    return ancestors


def _compute_invalidation_hash(root: Path, fixtures: list[Path]) -> str:
    """Return a hash that changes whenever any file in ``fixtures`` changes.

    Any change to a fixture file (conftests, helper modules like
    ``common.py``, ancestor conftests) invalidates the entire test-count
    cache.  This is coarse but safe: any of these can shift fixture
    parametrization in ways the cache cannot otherwise detect, so we
    just re-collect everything.

    Paths are encoded with ``os.path.relpath`` so the hash stays stable
    across machines and also covers ancestor conftests above ``root``
    (whose ``relative_to(root)`` would fail).
    """
    digest = hashlib.sha256()
    for fixture in fixtures:
        digest.update(os.path.relpath(fixture, root).encode())
        digest.update(b"\0")
        digest.update(fixture.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass
class _CacheEntry:
    """Cached test count for a single file."""

    hash: str
    count: int


@dataclass
class _Cache:
    """Mapping of test file path → cached entry, plus invalidation key."""

    invalidation_hash: str
    entries: dict[str, _CacheEntry]

    @classmethod
    def empty(cls, invalidation_hash: str = "") -> _Cache:
        """Return a new empty cache."""
        return cls(invalidation_hash=invalidation_hash, entries={})

    @classmethod
    def load(cls, path: Path, current_invalidation_hash: str) -> _Cache:
        """Load cache from ``path`` and invalidate it on schema/fixture drift.

        Any failure (missing file, bad JSON, version drift, fixture drift)
        returns an empty cache so the script just falls back to a full
        collection.  This is the self-healing path.
        """
        try:
            raw = json.loads(path.read_bytes())
        except OSError, ValueError:
            return cls.empty(current_invalidation_hash)
        if not isinstance(raw, dict) or raw.get("version") != _CACHE_VERSION:
            return cls.empty(current_invalidation_hash)
        if raw.get("invalidation_hash") != current_invalidation_hash:
            return cls.empty(current_invalidation_hash)
        files = raw.get("files")
        if not isinstance(files, dict):
            return cls.empty(current_invalidation_hash)
        entries: dict[str, _CacheEntry] = {}
        for key, value in files.items():
            if (
                not isinstance(value, dict)
                or not isinstance(value.get("hash"), str)
                or not isinstance(value.get("count"), int)
            ):
                # Skip malformed entries instead of discarding the whole cache.
                continue
            entries[key] = _CacheEntry(hash=value["hash"], count=value["count"])
        return cls(invalidation_hash=current_invalidation_hash, entries=entries)

    def save(self, path: Path) -> None:
        """Write the cache to ``path``."""
        path.write_text(
            json.dumps(
                {
                    "version": _CACHE_VERSION,
                    "invalidation_hash": self.invalidation_hash,
                    "files": {
                        key: {"hash": entry.hash, "count": entry.count}
                        for key, entry in sorted(self.entries.items())
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )


def _resolve_from_cache(
    test_files: list[Path],
    cache: _Cache,
    root: Path,
) -> tuple[dict[Path, _CacheEntry], dict[Path, str]]:
    """Split ``test_files`` into ``(cached_entries, miss_hashes)``.

    A file is served from cache when its content hash matches what we
    previously stored; otherwise it is queued for re-collection.  Each
    file is hashed exactly once: hits carry the stored hash forward,
    misses carry the just-computed hash so the rebuild step doesn't
    re-read the same bytes a second time.
    """
    hits: dict[Path, _CacheEntry] = {}
    miss_hashes: dict[Path, str] = {}
    for file in test_files:
        file_hash = _hash_file(file)
        entry = cache.entries.get(str(file.relative_to(root)))
        if entry is not None and entry.hash == file_hash:
            hits[file] = entry
        else:
            miss_hashes[file] = file_hash
    return hits, miss_hashes


def _run_collect_batches(paths: list[Path]) -> list[tuple[str, str, int]]:
    """Run pytest --collect-only across ``paths`` using a process pool."""
    workers = min(len(paths), os.cpu_count() or 1) or 1
    batches = [paths[i::workers] for i in range(workers)]
    if workers == 1:
        return [_collect_batch(batches[0])]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(_collect_batch, batches))


def _parse_collect_output(stdout: str) -> dict[Path, int]:
    """Parse ``pytest --collect-only -qq`` output into ``{path: count}``."""
    counts: dict[Path, int] = {}
    for line in stdout.splitlines():
        if not line.strip():
            continue
        file_path, _, total_tests = line.partition(": ")
        if not file_path or not total_tests:
            raise ValueError(f"Unexpected line: {line}")
        counts[Path(file_path)] = int(total_tests)
    return counts


def _run_pytest_collect(paths: list[Path]) -> dict[Path, int]:
    """Run pytest --collect-only across ``paths`` and parse the output."""
    counts: dict[Path, int] = {}
    for stdout, stderr, returncode in _run_collect_batches(paths):
        if returncode != 0:
            print("Failed to collect tests:")
            print(stderr)
            print(stdout)
            sys.exit(1)
        try:
            counts.update(_parse_collect_output(stdout))
        except ValueError as err:
            print(err)
            sys.exit(1)
    return counts


def _build_folder(root: Path, counts: dict[Path, int]) -> TestFolder:
    """Build a ``TestFolder`` from a flat ``{path: count}`` mapping.

    Files reported with zero tests are skipped so they don't enter
    bucketing (helper modules named ``test_*.py`` with no test functions
    look like test files to the walker but pytest returns nothing for
    them).
    """
    folder = TestFolder(root)
    for file_path, count in counts.items():
        if count:
            folder.add_test_file(TestFile(count, file_path))
    return folder


def _exit_if_empty(paths: list[Path], root: Path) -> None:
    """Exit with a clear message when no eligible test paths were found."""
    if not paths:
        print(f"No eligible test paths found under {root}")
        sys.exit(1)


def _collect_tests_uncached(path: Path) -> TestFolder:
    """Collect tests by handing pytest the top-level directories.

    Skips the tree walk and per-file hashing; used when no cache file is
    requested so the script behaves like the pre-cache implementation.
    """
    batch_paths = _enumerate_batch_paths(path)
    _exit_if_empty(batch_paths, path)
    return _build_folder(path, _run_pytest_collect(batch_paths))


def _collect_tests_cached(path: Path, cache_path: Path) -> TestFolder:
    """Collect tests using an on-disk cache for incremental updates."""
    all_test_files, fixtures = _walk_test_tree(path)
    _exit_if_empty(all_test_files, path)

    # Include ancestor conftests so a subtree run (eg tests/components)
    # still invalidates when tests/conftest.py changes.
    all_fixtures = _find_ancestor_conftests(path) + fixtures
    invalidation_hash = _compute_invalidation_hash(path, all_fixtures)
    cache = _Cache.load(cache_path, invalidation_hash)

    hits, miss_hashes = _resolve_from_cache(all_test_files, cache, path)
    print(
        f"Cache: {len(hits)} hits / {len(miss_hashes)} misses"
        f" / {len(all_test_files)} total"
    )

    new_counts: dict[Path, int] = {}
    if miss_hashes:
        # On a full cold-cache run, hand pytest the top-level directories
        # instead of 5000+ individual file paths: pytest walks dirs much
        # faster than it resolves each file argument.  Once any cache hits
        # exist, use file-level collection so we only re-collect the diff.
        collect_paths = _enumerate_batch_paths(path) if not hits else list(miss_hashes)
        new_counts = _run_pytest_collect(collect_paths)

    # Walk the full set of test files once and decide each file's entry:
    # hits keep their stored entry (and verified hash), misses build a
    # fresh entry from the resolve-time hash plus the freshly collected
    # count.  Files in misses that pytest returned no count for are
    # stored as 0 so they stop re-collecting on the next run.
    entries: dict[str, _CacheEntry] = {}
    counts: dict[Path, int] = {}
    for file in all_test_files:
        if (entry := hits.get(file)) is None:
            entry = _CacheEntry(hash=miss_hashes[file], count=new_counts.get(file, 0))
        entries[str(file.relative_to(path))] = entry
        counts[file] = entry.count
    _Cache(invalidation_hash=invalidation_hash, entries=entries).save(cache_path)
    return _build_folder(path, counts)


def collect_tests(path: Path, cache_path: Path | None = None) -> TestFolder:
    """Collect all tests, using an on-disk cache when ``cache_path`` is set."""
    if cache_path is None:
        return _collect_tests_uncached(path)
    if path.is_file():
        # The cache keys on conftest_hash, but a single file root has no
        # ancestor conftests to walk and the hash would always be empty,
        # which would let stale counts survive conftest edits.  Skip the
        # cache for the file-root case rather than silently mis-caching.
        print(f"--cache ignored: {path} is a single file")
        return _collect_tests_uncached(path)
    return _collect_tests_cached(path, cache_path)


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
        "--cache",
        help="Path to a JSON file used to cache per-file test counts",
        type=Path,
        default=None,
    )

    arguments = parser.parse_args()

    print("Collecting tests...")
    tests = collect_tests(arguments.path, arguments.cache)
    tests_per_bucket = ceil(tests.total_tests / arguments.bucket_count)

    bucket_holder = BucketHolder(tests_per_bucket, arguments.bucket_count)
    print("Splitting tests...")
    bucket_holder.split_tests(tests)

    print(f"Total tests: {tests.total_tests}")
    print(f"Estimated tests per bucket: {tests_per_bucket}")

    bucket_holder.create_output_file()


if __name__ == "__main__":
    main()
