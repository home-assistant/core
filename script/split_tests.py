#!/usr/bin/env python3
"""Helper script to split test into n buckets."""

import argparse
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from contextlib import suppress
from dataclasses import dataclass, field, replace
import hashlib
import json
from math import ceil
from operator import attrgetter, itemgetter
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
_CACHE_VERSION: Final = 1

# Fall back from file-level to directory-level pytest collection when
# misses make up more than this fraction of the tree; past that point
# the per-file argv overhead pytest pays outweighs the cost of letting
# it re-walk dirs and re-collect the hits.
_DIR_LEVEL_MISS_RATIO: Final = 0.3


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
        """Place atomic units via best-fit; oversized ones go to the smallest bucket."""
        digits = len(str(test_folder.total_tests))
        by_load = attrgetter("total_tests")
        units = sorted(self._atomic_units(test_folder), key=itemgetter(0), reverse=True)
        for size, items in units:
            fits = [
                b
                for b in self._buckets
                if b.total_tests + size <= self._tests_per_bucket
            ]
            bucket = max(fits, key=by_load) if fits else min(self._buckets, key=by_load)
            for item in items:
                tag = " (same bucket)" if item is not items[0] else ""
                print(f"{item.total_tests:>{digits}} tests in {item.path}{tag}")
                bucket.add(item)

        if not test_folder.added_to_bucket:
            raise ValueError("Not all tests are added to a bucket")

    def _atomic_units(
        self, folder: TestFolder
    ) -> Iterator[tuple[int, list[TestFolder | TestFile]]]:
        """Yield ``(size, items)`` placement units.

        A folder that fits is one unit; otherwise same-dir files form
        a unit only when the folder has syrupy snapshots, else each
        file stands alone.  Sub-folders recurse independently.
        """
        if folder.total_tests <= self._tests_per_bucket:
            yield folder.total_tests, [folder]
            return

        sibling_files = [c for c in folder.children.values() if isinstance(c, TestFile)]
        if sibling_files:
            if _has_snapshots(folder.path):
                yield (
                    sum(f.total_tests for f in sibling_files),
                    list(sibling_files),
                )
            else:
                for file in sibling_files:
                    yield file.total_tests, [file]
        for child in folder.children.values():
            if isinstance(child, TestFolder):
                yield from self._atomic_units(child)

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


def _has_snapshots(folder_path: Path) -> bool:
    """Return True when ``folder_path/snapshots`` holds ``.ambr`` files.

    Same-dir tests must share a pytest run so syrupy can spot unused
    snapshots; without snapshots that constraint doesn't apply.
    """
    return any((folder_path / "snapshots").glob("*.ambr"))


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


def _hash_file(path: Path) -> str:
    """Return a short content hash for ``path``."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _walk_test_tree(root: Path) -> tuple[list[Path], list[Path]]:
    """Walk ``root`` once and return (test files, fixture files).

    Fixtures are every non-``test_*.py`` ``.py``: conftests and helpers
    like ``common.py`` that drive parametrize imports.  Uses ``os.walk``
    (~2x faster than ``Path.rglob`` on this tree) and prunes ``.``/``_``
    subdirs.
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


_PROJECT_ROOT_MARKER: Final = "pyproject.toml"


def _find_ancestor_fixtures(root: Path) -> list[Path]:
    """Return non-``test_*.py`` Python files above ``root``, up to the project root.

    Includes conftests and helper modules (eg ``common.py``); subtree
    runs need both so shared ancestor helpers like
    ``tests/components/common.py`` still invalidate descendants.
    Stops at the first ancestor containing ``pyproject.toml`` so we
    don't read unrelated ``.py`` files outside the repo or trip on
    dirs we can't list.
    """
    fixtures: list[Path] = []
    current = root.resolve().parent
    while True:
        with suppress(OSError):
            fixtures.extend(
                entry
                for entry in current.glob("*.py")
                if not entry.name.startswith("test_")
            )
        if (current / _PROJECT_ROOT_MARKER).exists():
            break
        if current == current.parent:
            break
        current = current.parent
    return fixtures


def _build_fixtures_by_dir(
    root: Path, descendants: list[Path]
) -> dict[Path, list[Path]]:
    """Bucket descendants plus ancestor fixtures by resolved parent dir."""
    by_dir: dict[Path, list[Path]] = {}
    for fixture in (*_find_ancestor_fixtures(root), *descendants):
        by_dir.setdefault(fixture.parent.resolve(), []).append(fixture)
    return by_dir


def _file_fixture_hash(
    test_file: Path,
    root: Path,
    fixtures_by_dir: dict[Path, list[Path]],
    blob_cache: dict[Path, bytes] | None = None,
    dir_cache: dict[Path, str] | None = None,
) -> str:
    """Hash every ``.py`` fixture on the test file's ancestor path.

    Catches conftests and helper modules (``common.py`` etc.) at any
    level so parametrize imports from shared helpers invalidate
    descendants, while sibling subtrees stay warm.  Pass shared
    ``blob_cache``/``dir_cache`` dicts to memoize across many files.
    """
    test_dir = test_file.parent.resolve()
    if dir_cache is not None and (cached := dir_cache.get(test_dir)) is not None:
        return cached
    relevant: list[Path] = []
    current = test_dir
    while True:
        relevant.extend(fixtures_by_dir.get(current, ()))
        parent = current.parent
        if parent == current:
            break
        current = parent
    relevant.sort()
    digest = hashlib.sha256()
    for fixture in relevant:
        blob = blob_cache.get(fixture) if blob_cache is not None else None
        if blob is None:
            # relpath keeps the hash machine-stable across ancestor paths.
            blob = (
                os.path.relpath(fixture, root).encode()
                + b"\0"
                + fixture.read_bytes()
                + b"\0"
            )
            if blob_cache is not None:
                blob_cache[fixture] = blob
        digest.update(blob)
    result = digest.hexdigest()
    if dir_cache is not None:
        dir_cache[test_dir] = result
    return result


@dataclass
class _CacheEntry:
    """Cached test count plus its scope hash for a single file."""

    hash: str
    fixture_hash: str
    count: int


@dataclass
class _Cache:
    """Mapping of test file path → cached entry."""

    entries: dict[str, _CacheEntry]

    @classmethod
    def load(cls, path: Path) -> _Cache:
        """Load cache; any drift (missing, bad, version, malformed) returns empty."""
        try:
            raw = json.loads(path.read_bytes())
        except OSError, ValueError:
            raw = None
        if not (
            isinstance(raw, dict)
            and raw.get("version") == _CACHE_VERSION
            and isinstance(raw.get("files"), dict)
        ):
            return cls(entries={})
        entries: dict[str, _CacheEntry] = {}
        for key, value in raw["files"].items():
            if not isinstance(value, dict):
                continue
            hash_value = value.get("hash")
            fixture_hash = value.get("fixture_hash")
            count = value.get("count")
            # bool is an int subclass; reject true/false and negatives so
            # corrupted JSON can't feed bucket sizing a bogus weight.
            if (
                not isinstance(hash_value, str)
                or not isinstance(fixture_hash, str)
                or not isinstance(count, int)
                or isinstance(count, bool)
                or count < 0
            ):
                continue
            entries[key] = _CacheEntry(
                hash=hash_value, fixture_hash=fixture_hash, count=count
            )
        return cls(entries=entries)

    def save(self, path: Path) -> None:
        """Write the cache to ``path``, creating parent dirs as needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "version": _CACHE_VERSION,
                    "files": {
                        key: {
                            "hash": entry.hash,
                            "fixture_hash": entry.fixture_hash,
                            "count": entry.count,
                        }
                        for key, entry in sorted(self.entries.items())
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )


def _resolve_entries(
    test_files: list[Path],
    cache: _Cache,
    root: Path,
    fixtures_by_dir: dict[Path, list[Path]],
) -> tuple[dict[Path, _CacheEntry], list[Path]]:
    """Build an entry for every file; return ``(entries, misses)``.

    Hits reuse the stored entry; misses get fresh hashes with a
    count=0 placeholder for the caller to fill in after pytest runs.
    Shared caches memoize fixture blobs and per-dir hashes so each
    fixture file is read once and each unique dir hashed once.
    """
    blob_cache: dict[Path, bytes] = {}
    dir_cache: dict[Path, str] = {}
    entries: dict[Path, _CacheEntry] = {}
    misses: list[Path] = []
    for file in test_files:
        file_hash = _hash_file(file)
        fixture_hash = _file_fixture_hash(
            file, root, fixtures_by_dir, blob_cache, dir_cache
        )
        cached = cache.entries.get(str(file.relative_to(root)))
        if (
            cached is not None
            and cached.hash == file_hash
            and cached.fixture_hash == fixture_hash
        ):
            entries[file] = cached
        else:
            entries[file] = _CacheEntry(
                hash=file_hash, fixture_hash=fixture_hash, count=0
            )
            misses.append(file)
    return entries, misses


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
        # Surface stderr from successful runs too; pytest puts deprecation
        # and import warnings here that would otherwise vanish.
        if stderr.strip():
            sys.stderr.write(stderr)
        try:
            counts.update(_parse_collect_output(stdout))
        except ValueError as err:
            print(err)
            sys.exit(1)
    return counts


def _build_folder(root: Path, counts: dict[Path, int]) -> TestFolder:
    """Build a ``TestFolder`` from ``{path: count}``; zero-count files are skipped."""
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
    """Hand pytest the top-level dirs; the pre-cache path when ``--cache`` is unset."""
    batch_paths = _enumerate_batch_paths(path)
    _exit_if_empty(batch_paths, path)
    return _build_folder(path, _run_pytest_collect(batch_paths))


def _collect_tests_cached(path: Path, cache_path: Path) -> TestFolder:
    """Collect tests using an on-disk cache for incremental updates."""
    all_test_files, fixtures = _walk_test_tree(path)
    _exit_if_empty(all_test_files, path)

    fixtures_by_dir = _build_fixtures_by_dir(path, fixtures)
    cache = _Cache.load(cache_path)
    entries, misses = _resolve_entries(all_test_files, cache, path, fixtures_by_dir)
    hits = len(all_test_files) - len(misses)
    print(f"Cache: {hits} hits / {len(misses)} misses / {len(all_test_files)} total")

    if misses:
        # Past _DIR_LEVEL_MISS_RATIO the per-file argv overhead beats
        # re-walking the dirs, so fall back to dir-level collection.
        if not hits or len(misses) > len(all_test_files) * _DIR_LEVEL_MISS_RATIO:
            collect_paths = _enumerate_batch_paths(path)
        else:
            collect_paths = misses
        new_counts = _run_pytest_collect(collect_paths)
        # Files pytest returned no count for stay at 0; cached so they
        # aren't re-collected next run.
        for file in misses:
            entries[file] = replace(entries[file], count=new_counts.get(file, 0))

    _Cache(entries={str(f.relative_to(path)): e for f, e in entries.items()}).save(
        cache_path
    )
    return _build_folder(path, {f: e.count for f, e in entries.items()})


def collect_tests(path: Path, cache_path: Path | None = None) -> TestFolder:
    """Collect all tests, using an on-disk cache when ``cache_path`` is set."""
    if cache_path is None:
        return _collect_tests_uncached(path)
    if path.is_file():
        # No fixture tree to scope against; bypass cache to avoid stale hits.
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
