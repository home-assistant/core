"""Tests for the split_tests cache logic."""

from collections.abc import Callable
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from script import split_tests


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """Build a tree: root conftest, two integrations, a ``common.py`` helper."""
    # Bound the ancestor-fixture walk so it doesn't escape tmp_path.
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "conftest.py").write_text("# tests/conftest.py\n")
    (tmp_path / "common.py").write_text("# helper module\n")

    alpha_dir = tmp_path / "components" / "alpha"
    alpha_dir.mkdir(parents=True)
    (alpha_dir / "conftest.py").write_text("# alpha conftest\n")
    (alpha_dir / "test_one.py").write_text("def test_a():\n    pass\n")
    (alpha_dir / "test_two.py").write_text("def test_b():\n    pass\n")

    beta_dir = tmp_path / "components" / "beta"
    beta_dir.mkdir()
    (beta_dir / "test_x.py").write_text("def test_x():\n    pass\n")

    return tmp_path


def test_iter_eligible_children_filters_helpers(tree: Path) -> None:
    """Helper files like conftest.py and common.py are not collection targets."""
    children = split_tests._iter_eligible_children(tree)
    names = {p.name for p in children}
    assert "common.py" not in names
    assert "conftest.py" not in names
    # components/ is a dir, gets included.
    assert "components" in names


def test_enumerate_batch_paths_fans_out_components(tree: Path) -> None:
    """tests/components fans out one level deeper into per-integration paths."""
    paths = split_tests._enumerate_batch_paths(tree)
    rel = {p.relative_to(tree).as_posix() for p in paths}
    assert rel == {"components/beta", "components/alpha"}


def test_enumerate_batch_paths_for_single_file(tmp_path: Path) -> None:
    """A test file passed directly is returned as-is."""
    file = tmp_path / "test_solo.py"
    file.write_text("def test_x(): pass\n")
    assert split_tests._enumerate_batch_paths(file) == [file]


def _fixture_hash_for(tree: Path, file: Path) -> str:
    """Compute the fixture scope hash for ``file`` rooted at ``tree``."""
    _, fixtures = split_tests._walk_test_tree(tree)
    fixtures_by_dir = split_tests._build_fixtures_by_dir(tree, fixtures)
    return split_tests._file_fixture_hash(file, tree, fixtures_by_dir)


def _prime_cache(
    cache_path: Path,
    tree: Path,
    hits: dict[Path, int] | None = None,
    extra_entries: dict[str, split_tests._CacheEntry] | None = None,
) -> None:
    """Save a cache for ``tree`` keyed on real file and fixture hashes.

    ``hits`` maps file → cached count (hashed for real, so the next
    run resolves as a hit).  ``extra_entries`` injects raw entries
    whose path may not exist on disk (eg ghost files).
    """
    entries: dict[str, split_tests._CacheEntry] = {
        str(file.relative_to(tree)): split_tests._CacheEntry(
            hash=split_tests._hash_file(file),
            fixture_hash=_fixture_hash_for(tree, file),
            count=count,
        )
        for file, count in (hits or {}).items()
    }
    if extra_entries:
        entries.update(extra_entries)
    split_tests._Cache(entries=entries).save(cache_path)


def _echo_one_test_each(
    skip: set[Path] | None = None,
) -> Callable[[list[Path]], list[tuple[str, str, int]]]:
    """Fake ``_run_collect_batches``: 1 test per path; ``skip`` paths drop out."""
    skip = skip or set()

    def fake(paths: list[Path]) -> list[tuple[str, str, int]]:
        emitted = [p for p in paths if p not in skip]
        return [("\n".join(f"{p}: 1" for p in emitted) + "\n", "", 0)]

    return fake


def test_file_fixture_hash_changes_when_ancestor_conftest_changes(tree: Path) -> None:
    """A conftest edit in the file's ancestor chain busts that file's hash."""
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    before = _fixture_hash_for(tree, alpha_one)
    # Same-dir conftest is an ancestor of alpha_one.
    (tree / "components" / "alpha" / "conftest.py").write_text("# changed\n")
    after = _fixture_hash_for(tree, alpha_one)
    assert before != after


def test_file_fixture_hash_changes_when_same_dir_helper_changes(tree: Path) -> None:
    """A non-conftest helper in the same dir busts the file's hash."""
    alpha_dir = tree / "components" / "alpha"
    (alpha_dir / "common.py").write_text("# helper v1\n")
    alpha_one = alpha_dir / "test_one.py"
    before = _fixture_hash_for(tree, alpha_one)
    (alpha_dir / "common.py").write_text("# helper v2\n")
    after = _fixture_hash_for(tree, alpha_one)
    assert before != after


def test_file_fixture_hash_isolated_from_sibling_dir(tree: Path) -> None:
    """A helper change in a sibling subtree leaves this file's hash alone."""
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    before = _fixture_hash_for(tree, alpha_one)
    # beta is a sibling of alpha (not an ancestor), so its helper edit
    # must not affect alpha_one's fixture hash.
    (tree / "components" / "beta" / "common.py").write_text("# beta v2\n")
    after = _fixture_hash_for(tree, alpha_one)
    assert before == after


def test_file_fixture_hash_changes_when_ancestor_helper_changes(tree: Path) -> None:
    """A helper edit anywhere on the ancestor path busts the file's hash.

    Test files often import VALUES for ``@pytest.mark.parametrize`` from
    shared helpers like ``tests/components/common.py``; any ancestor
    ``.py`` change has to invalidate descendants so cached counts don't
    drift after edits to those sources.
    """
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    # Seed a shared helper one level up from alpha.
    components_common = tree / "components" / "common.py"
    components_common.write_text("# helper v1\n")
    before = _fixture_hash_for(tree, alpha_one)
    components_common.write_text("# helper v2\n")
    after = _fixture_hash_for(tree, alpha_one)
    assert before != after


def test_file_fixture_hash_stable_for_test_changes(tree: Path) -> None:
    """Test-file edits do not invalidate the file's fixture hash."""
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    before = _fixture_hash_for(tree, alpha_one)
    alpha_one.write_text("def test_a():\n    pass\n\ndef test_c():\n    pass\n")
    after = _fixture_hash_for(tree, alpha_one)
    assert before == after


def test_find_ancestor_fixtures_stops_at_project_root(tmp_path: Path) -> None:
    """A project-root marker bounds the ancestor walk."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text("")
    (project / "common.py").write_text("# included\n")
    nested = project / "tests" / "x"
    nested.mkdir(parents=True)
    # Above the project root: must NOT be picked up.
    (tmp_path / "outside.py").write_text("# excluded\n")

    found = {p.name for p in split_tests._find_ancestor_fixtures(nested)}
    assert "common.py" in found
    assert "outside.py" not in found


def test_find_ancestor_fixtures_walks_through_gaps(tmp_path: Path) -> None:
    """Ancestor conftests + helpers are collected across intermediate gaps."""
    (tmp_path / "pyproject.toml").write_text("")  # bound the walk
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    # ``a/b`` has no fixtures, but ``a`` has both a conftest and a helper.
    (tmp_path / "a" / "conftest.py").write_text("# a\n")
    (tmp_path / "a" / "common.py").write_text("# a helper\n")
    (tmp_path / "a" / "b" / "c" / "conftest.py").write_text("# c\n")

    found = {
        p.relative_to(tmp_path).as_posix()
        for p in split_tests._find_ancestor_fixtures(nested)
    }
    # The walk starts at ``nested.parent`` (a/b); a/b/c/conftest.py is
    # not an ancestor.  Both ``a/conftest.py`` and ``a/common.py`` must
    # be found despite a/b having no fixtures of its own.
    assert "a/conftest.py" in found
    assert "a/common.py" in found
    assert "a/b/c/conftest.py" not in found


def test_file_fixture_hash_picks_up_ancestor_helper_above_root(
    tmp_path: Path,
) -> None:
    """An ancestor non-conftest helper above root still busts descendant hashes.

    A subtree run on ``components/`` must still invalidate when a shared
    helper one level up (eg ``tests/components/common.py``) changes.
    """
    (tmp_path / "pyproject.toml").write_text("")  # bound the walk
    (tmp_path / "common.py").write_text("# v1\n")
    subtree = tmp_path / "components"
    subtree.mkdir()
    test_file = subtree / "test_x.py"
    test_file.write_text("def test_x(): pass\n")

    before = _fixture_hash_for(subtree, test_file)
    (tmp_path / "common.py").write_text("# v2\n")
    after = _fixture_hash_for(subtree, test_file)
    assert before != after


def test_file_fixture_hash_picks_up_ancestor_conftest_across_gap(
    tmp_path: Path,
) -> None:
    """An ancestor conftest across a gap still busts the descendant's hash."""
    (tmp_path / "pyproject.toml").write_text("")  # bound the walk
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (tmp_path / "a" / "conftest.py").write_text("# v1\n")
    test_file = nested / "test_x.py"
    test_file.write_text("def test_x(): pass\n")

    before = _fixture_hash_for(nested, test_file)
    (tmp_path / "a" / "conftest.py").write_text("# v2\n")
    after = _fixture_hash_for(nested, test_file)
    assert before != after


def test_file_fixture_hash_includes_ancestor_above_root(tmp_path: Path) -> None:
    """An ancestor conftest above root must still scope a subtree file."""
    (tmp_path / "pyproject.toml").write_text("")  # bound the walk
    (tmp_path / "conftest.py").write_text("# parent\n")
    subtree = tmp_path / "components"
    subtree.mkdir()
    test_file = subtree / "test_x.py"
    test_file.write_text("def test_x(): pass\n")

    before = _fixture_hash_for(subtree, test_file)
    (tmp_path / "conftest.py").write_text("# parent changed\n")
    after = _fixture_hash_for(subtree, test_file)
    assert before != after


def test_walk_test_tree_separates_tests_from_fixtures(tree: Path) -> None:
    """The walker returns test_*.py files and every other .py as fixtures."""
    test_files, fixtures = split_tests._walk_test_tree(tree)
    test_names = {p.name for p in test_files}
    fixture_paths = {p.relative_to(tree).as_posix() for p in fixtures}
    assert test_names == {"test_one.py", "test_two.py", "test_x.py"}
    assert fixture_paths == {
        "conftest.py",
        "common.py",
        "components/alpha/conftest.py",
    }


def test_walk_test_tree_skips_hidden_and_dunder_dirs(tmp_path: Path) -> None:
    """Hidden/dunder directories are pruned from the walk."""
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "test_ghost.py").write_text("def test_g(): pass\n")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "test_invisible.py").write_text("def test_h(): pass\n")
    (tmp_path / "test_real.py").write_text("def test_r(): pass\n")

    test_files, _ = split_tests._walk_test_tree(tmp_path)
    assert {p.name for p in test_files} == {"test_real.py"}


def test_collect_tests_skips_cache_for_single_file_root(tmp_path: Path) -> None:
    """Single-file root bypasses caching.

    Otherwise the invalidation hash would be constant and stale counts
    could survive conftest edits.
    """
    cache_path = tmp_path / "cache.json"
    file = tmp_path / "test_solo.py"
    file.write_text("def test_x(): pass\n")

    with (
        patch.object(split_tests, "_collect_tests_uncached") as uncached,
        patch.object(split_tests, "_collect_tests_cached") as cached,
    ):
        split_tests.collect_tests(file, cache_path)

    uncached.assert_called_once_with(file)
    cached.assert_not_called()
    assert not cache_path.exists()


def test_cache_roundtrip(tmp_path: Path) -> None:
    """A cache survives save → load."""
    cache_path = tmp_path / "cache.json"
    cache = split_tests._Cache(
        entries={
            "tests/alpha/test_a.py": split_tests._CacheEntry(
                hash="h1", fixture_hash="f1", count=5
            )
        },
    )
    cache.save(cache_path)
    loaded = split_tests._Cache.load(cache_path)
    assert loaded.entries == cache.entries


def test_cache_load_missing_returns_empty(tmp_path: Path) -> None:
    """A missing cache file degrades gracefully to an empty cache."""
    cache = split_tests._Cache.load(tmp_path / "missing.json")
    assert cache.entries == {}


def test_cache_load_invalid_json_returns_empty(tmp_path: Path) -> None:
    """Corrupt JSON is treated as a cache miss instead of crashing."""
    path = tmp_path / "broken.json"
    path.write_text("{not json")
    cache = split_tests._Cache.load(path)
    assert cache.entries == {}


def test_cache_load_wrong_version_returns_empty(tmp_path: Path) -> None:
    """An older cache schema is discarded rather than misread."""
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"version": 0, "files": {}}))
    cache = split_tests._Cache.load(path)
    assert cache.entries == {}


def test_cache_load_drops_malformed_entries(tmp_path: Path) -> None:
    """Malformed per-file entries are skipped, valid ones are kept."""
    path = tmp_path / "cache.json"
    path.write_text(
        json.dumps(
            {
                "version": split_tests._CACHE_VERSION,
                "files": {
                    "good.py": {"hash": "h1", "fixture_hash": "f1", "count": 3},
                    "bad_count.py": {
                        "hash": "h2",
                        "fixture_hash": "f2",
                        "count": "three",
                    },
                    "missing_hash.py": {"fixture_hash": "f3", "count": 4},
                    "missing_fixture_hash.py": {"hash": "h4", "count": 4},
                    "not_dict.py": 5,
                    "negative_count.py": {
                        "hash": "h5",
                        "fixture_hash": "f5",
                        "count": -1,
                    },
                },
            }
        )
    )
    cache = split_tests._Cache.load(path)
    assert set(cache.entries) == {"good.py"}


def test_cache_save_creates_parent_dir(tmp_path: Path) -> None:
    """Save mkdirs missing parent dirs so ``--cache foo/bar.json`` works."""
    cache_path = tmp_path / "nested" / "subdir" / "cache.json"
    split_tests._Cache(entries={}).save(cache_path)
    assert cache_path.is_file()


def _resolve(
    test_files: list[Path], cache: split_tests._Cache, tree: Path
) -> tuple[dict[Path, split_tests._CacheEntry], list[Path]]:
    """Run resolve_entries with a freshly indexed fixtures_by_dir."""
    _, fixtures = split_tests._walk_test_tree(tree)
    return split_tests._resolve_entries(
        test_files,
        cache,
        tree,
        split_tests._build_fixtures_by_dir(tree, fixtures),
    )


def test_resolve_entries_hits_and_misses(tree: Path) -> None:
    """Files with matching content + fixture hashes are hits."""
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    alpha_two = tree / "components" / "alpha" / "test_two.py"
    beta_x = tree / "components" / "beta" / "test_x.py"

    alpha_one_hash = split_tests._hash_file(alpha_one)
    alpha_one_fixture = _fixture_hash_for(tree, alpha_one)
    cache = split_tests._Cache(
        entries={
            str(alpha_one.relative_to(tree)): split_tests._CacheEntry(
                hash=alpha_one_hash, fixture_hash=alpha_one_fixture, count=1
            ),
            str(alpha_two.relative_to(tree)): split_tests._CacheEntry(
                hash="stale", fixture_hash=alpha_one_fixture, count=99
            ),
        },
    )
    entries, misses = _resolve([alpha_one, alpha_two, beta_x], cache, tree)
    # Hit: cached entry passed through verbatim.
    assert entries[alpha_one] == split_tests._CacheEntry(
        hash=alpha_one_hash, fixture_hash=alpha_one_fixture, count=1
    )
    # Misses: fresh hashes plus a count=0 placeholder.
    assert set(misses) == {alpha_two, beta_x}
    assert entries[alpha_two].count == 0
    assert entries[alpha_two].hash == split_tests._hash_file(alpha_two)
    assert entries[beta_x].count == 0
    assert entries[beta_x].hash == split_tests._hash_file(beta_x)


def test_resolve_entries_misses_on_fixture_drift(tree: Path) -> None:
    """A file with unchanged content but changed scope counts as a miss."""
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    cache = split_tests._Cache(
        entries={
            str(alpha_one.relative_to(tree)): split_tests._CacheEntry(
                hash=split_tests._hash_file(alpha_one),
                fixture_hash="stale-fixture-hash",
                count=1,
            ),
        },
    )
    _, misses = _resolve([alpha_one], cache, tree)
    assert misses == [alpha_one]


def test_resolve_entries_isolates_unrelated_dirs(tree: Path) -> None:
    """Editing a helper in one dir leaves files in other dirs as hits."""
    alpha_dir = tree / "components" / "alpha"
    beta_dir = tree / "components" / "beta"
    # Helpers per dir, so a change in alpha doesn't bust beta.
    (alpha_dir / "common.py").write_text("# alpha helper v1\n")
    (beta_dir / "common.py").write_text("# beta helper v1\n")
    alpha_one = alpha_dir / "test_one.py"
    beta_x = beta_dir / "test_x.py"

    # Snapshot cache entries with the v1 fixture state.
    cache = split_tests._Cache(
        entries={
            str(alpha_one.relative_to(tree)): split_tests._CacheEntry(
                hash=split_tests._hash_file(alpha_one),
                fixture_hash=_fixture_hash_for(tree, alpha_one),
                count=1,
            ),
            str(beta_x.relative_to(tree)): split_tests._CacheEntry(
                hash=split_tests._hash_file(beta_x),
                fixture_hash=_fixture_hash_for(tree, beta_x),
                count=2,
            ),
        },
    )

    # Now bust beta's helper; alpha's scope is unchanged, beta's isn't.
    (beta_dir / "common.py").write_text("# beta helper v2\n")
    _, misses = _resolve([alpha_one, beta_x], cache, tree)
    assert misses == [beta_x]


def test_collect_tests_hashes_each_file_once(tree: Path) -> None:
    """Hits reuse the stored hash, misses reuse the resolve-time hash.

    Guards against regressing the double-read on cache-miss rebuilds:
    each test file should pass through _hash_file at most once per run.
    """
    cache_path = tree / "cache.json"
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    # Prime with one hit so we exercise the file-level (not directory-level) miss path.
    _prime_cache(cache_path, tree, hits={alpha_one: 1})

    real_hash = split_tests._hash_file
    counts: dict[Path, int] = {}

    def counting_hash(path: Path) -> str:
        counts[path] = counts.get(path, 0) + 1
        return real_hash(path)

    # Pin the threshold so the tiny tree stays on the file-level path.
    with (
        patch.object(split_tests, "_DIR_LEVEL_MISS_RATIO", 1.0),
        patch.object(split_tests, "_hash_file", side_effect=counting_hash),
        patch.object(
            split_tests, "_run_collect_batches", side_effect=_echo_one_test_each()
        ),
    ):
        split_tests.collect_tests(tree, cache_path)

    assert all(n == 1 for n in counts.values()), counts


def test_collect_tests_warm_cache_skips_pytest(tree: Path) -> None:
    """A warm cache with no diffs should skip the pytest subprocess entirely."""
    cache_path = tree / "cache.json"
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    alpha_two = tree / "components" / "alpha" / "test_two.py"
    beta_x = tree / "components" / "beta" / "test_x.py"
    _prime_cache(cache_path, tree, hits={alpha_one: 1, alpha_two: 2, beta_x: 3})

    with patch.object(split_tests, "_run_collect_batches") as run_batches:
        folder = split_tests.collect_tests(tree, cache_path)
    run_batches.assert_not_called()
    assert folder.total_tests == 6


def test_collect_tests_cold_cache_collects_only_missing(tree: Path) -> None:
    """A partial cache should only re-collect the files that changed."""
    cache_path = tree / "cache.json"
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    alpha_two = tree / "components" / "alpha" / "test_two.py"
    beta_x = tree / "components" / "beta" / "test_x.py"

    _prime_cache(cache_path, tree, hits={alpha_one: 1})

    with (
        patch.object(split_tests, "_DIR_LEVEL_MISS_RATIO", 1.0),
        patch.object(
            split_tests, "_run_collect_batches", side_effect=_echo_one_test_each()
        ) as run_batches,
    ):
        folder = split_tests.collect_tests(tree, cache_path)

    assert run_batches.call_count == 1
    requested = set(run_batches.call_args.args[0])
    assert requested == {alpha_two, beta_x}
    assert folder.total_tests == 3

    # Cache should now contain entries for every test file.
    saved = json.loads(cache_path.read_text())
    assert set(saved["files"]) == {
        str(alpha_one.relative_to(tree)),
        str(alpha_two.relative_to(tree)),
        str(beta_x.relative_to(tree)),
    }


def test_collect_tests_falls_back_to_dirs_when_misses_dominate(tree: Path) -> None:
    """Heavy misses should switch back to dir-level invocation."""
    cache_path = tree / "cache.json"
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    _prime_cache(cache_path, tree, hits={alpha_one: 1})
    # 2 misses / 3 total = 67% miss, above the 30% default threshold; this
    # also covers the new-directory PR case (mostly-new test files).

    with patch.object(
        split_tests, "_run_collect_batches", side_effect=_echo_one_test_each()
    ) as run_batches:
        split_tests.collect_tests(tree, cache_path)

    # We expect the dir-level batch paths, not the individual miss files.
    requested = set(run_batches.call_args.args[0])
    assert requested == set(split_tests._enumerate_batch_paths(tree))


def test_collect_tests_caches_files_with_no_collected_tests(tree: Path) -> None:
    """Files pytest returns nothing for are cached as 0 so we stop re-collecting them.

    Helper modules named test_*.py with no actual test functions look like
    test files to the walker but pytest reports no tests for them.  We
    want the cache to remember that and skip them on subsequent runs.
    """
    cache_path = tree / "cache.json"
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    alpha_two = tree / "components" / "alpha" / "test_two.py"
    beta_x = tree / "components" / "beta" / "test_x.py"

    # Prime the cache with one hit so collect_tests takes the file-level
    # diff path; the cold-cache path hands pytest top-level directories
    # rather than individual file paths.
    _prime_cache(cache_path, tree, hits={alpha_one: 1})

    with (
        patch.object(split_tests, "_DIR_LEVEL_MISS_RATIO", 1.0),
        patch.object(
            split_tests,
            "_run_collect_batches",
            side_effect=_echo_one_test_each(skip={alpha_two}),
        ),
    ):
        split_tests.collect_tests(tree, cache_path)

    saved = json.loads(cache_path.read_text())
    assert saved["files"][str(alpha_two.relative_to(tree))]["count"] == 0
    assert saved["files"][str(alpha_one.relative_to(tree))]["count"] == 1
    assert saved["files"][str(beta_x.relative_to(tree))]["count"] == 1

    # Re-running with the same content should now be a full cache hit
    # even though alpha_two has no tests.
    with patch.object(split_tests, "_run_collect_batches") as run_batches:
        folder = split_tests.collect_tests(tree, cache_path)
    run_batches.assert_not_called()
    # alpha_two contributes 0, only alpha_one + beta_x count.
    assert folder.total_tests == 2


def test_collect_tests_drops_deleted_files_from_cache(tree: Path) -> None:
    """Files that disappear from disk are dropped from the saved cache."""
    cache_path = tree / "cache.json"
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    ghost_rel = "components/alpha/test_ghost.py"

    _prime_cache(
        cache_path,
        tree,
        hits={alpha_one: 1},
        extra_entries={
            ghost_rel: split_tests._CacheEntry(
                hash="dead", fixture_hash="dead", count=42
            )
        },
    )

    with (
        patch.object(split_tests, "_DIR_LEVEL_MISS_RATIO", 1.0),
        patch.object(
            split_tests, "_run_collect_batches", side_effect=_echo_one_test_each()
        ),
    ):
        split_tests.collect_tests(tree, cache_path)

    saved = json.loads(cache_path.read_text())
    assert ghost_rel not in saved["files"]


def _build_folder(tree: Path, counts: dict[Path, int]) -> split_tests.TestFolder:
    """Build a TestFolder for ``tree`` populated with ``counts``."""
    folder = split_tests.TestFolder(tree)
    for path, n in counts.items():
        folder.add_test_file(split_tests.TestFile(n, path))
    return folder


def test_split_tests_keeps_siblings_together_when_snapshots_present(
    tmp_path: Path,
) -> None:
    """Same-dir files stay together when the folder has syrupy snapshots."""
    one = tmp_path / "alpha" / "test_one.py"
    two = tmp_path / "alpha" / "test_two.py"
    one.parent.mkdir(parents=True)
    one.touch()
    two.touch()
    # Add a snapshot so the syrupy constraint kicks in.
    snapshots = tmp_path / "alpha" / "snapshots"
    snapshots.mkdir()
    (snapshots / "test_one.ambr").write_text("")

    folder = _build_folder(tmp_path, {one: 60, two: 60})
    holder = split_tests.BucketHolder(tests_per_bucket=50, bucket_count=3)
    holder.split_tests(folder)
    # Both files must end up in one bucket; the other two stay empty.
    sizes = sorted(b.total_tests for b in holder._buckets)
    assert sizes == [0, 0, 120]


def test_split_tests_splits_siblings_when_no_snapshots(tmp_path: Path) -> None:
    """Same-dir files split freely across buckets when no snapshots exist."""
    one = tmp_path / "alpha" / "test_one.py"
    two = tmp_path / "alpha" / "test_two.py"
    one.parent.mkdir(parents=True)
    one.touch()
    two.touch()
    # No snapshots dir → free to split.

    folder = _build_folder(tmp_path, {one: 60, two: 60})
    holder = split_tests.BucketHolder(tests_per_bucket=70, bucket_count=2)
    holder.split_tests(folder)
    sizes = sorted(b.total_tests for b in holder._buckets)
    assert sizes == [60, 60]
