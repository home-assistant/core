"""Tests for the split_tests cache logic."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from script import split_tests


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """Build a small test tree on disk.

    Returns the root path containing one root conftest, two integrations,
    and a ``common.py`` helper that participates in cache invalidation
    but is not a pytest collection target.
    """
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


def _invalidation_hash_for(tree: Path) -> str:
    """Compute the invalidation hash for ``tree`` (helper for the tests below)."""
    _, fixtures = split_tests._walk_test_tree(tree)
    return split_tests._compute_invalidation_hash(tree, fixtures)


def test_compute_invalidation_hash_changes_when_conftest_changes(tree: Path) -> None:
    """Editing any conftest changes the global cache key."""
    before = _invalidation_hash_for(tree)
    (tree / "components" / "alpha" / "conftest.py").write_text("# changed\n")
    after = _invalidation_hash_for(tree)
    assert before != after


def test_compute_invalidation_hash_changes_when_helper_changes(tree: Path) -> None:
    """Editing a non-conftest helper (eg common.py imported for parametrize) busts the cache.

    Test files often import VALUES from common.py for
    @pytest.mark.parametrize; a change there shifts collected counts
    even though no test file or conftest was touched, so it has to
    participate in the invalidation hash.
    """
    before = _invalidation_hash_for(tree)
    (tree / "common.py").write_text("# helper changed\n")
    after = _invalidation_hash_for(tree)
    assert before != after


def test_compute_invalidation_hash_stable_for_test_changes(tree: Path) -> None:
    """Test-file edits do not invalidate the global cache key."""
    before = _invalidation_hash_for(tree)
    (tree / "components" / "alpha" / "test_one.py").write_text(
        "def test_a():\n    pass\n\ndef test_c():\n    pass\n"
    )
    after = _invalidation_hash_for(tree)
    assert before == after


def test_find_ancestor_conftests_walks_up_until_gap(tmp_path: Path) -> None:
    """Ancestor conftests are collected up to the first dir without one."""
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    # No conftest in tmp_path → walk stops there.
    (tmp_path / "a" / "conftest.py").write_text("# a\n")
    (tmp_path / "a" / "b" / "conftest.py").write_text("# b\n")

    ancestors = split_tests._find_ancestor_conftests(nested)
    assert [p.relative_to(tmp_path).as_posix() for p in ancestors] == [
        "a/b/conftest.py",
        "a/conftest.py",
    ]


def test_compute_invalidation_hash_changes_on_ancestor_change(tmp_path: Path) -> None:
    """An ancestor conftest edit must invalidate a subtree run's cache."""
    (tmp_path / "conftest.py").write_text("# parent\n")
    subtree = tmp_path / "components"
    subtree.mkdir()
    (subtree / "test_x.py").write_text("def test_x(): pass\n")

    def _hash() -> str:
        _, descendant = split_tests._walk_test_tree(subtree)
        ancestors = split_tests._find_ancestor_conftests(subtree)
        return split_tests._compute_invalidation_hash(subtree, ancestors + descendant)

    before = _hash()
    (tmp_path / "conftest.py").write_text("# parent changed\n")
    assert _hash() != before


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
    """A single-file root cannot validate conftest drift, so caching is disabled.

    _walk_test_tree returns no conftests for a file root, which would make
    the invalidation_hash a constant — letting a stale entry survive a real
    conftest change.  Better to bypass the cache than mis-cache silently.
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
    """A cache survives save → load when the conftest hash matches."""
    cache_path = tmp_path / "cache.json"
    cache = split_tests._Cache(
        invalidation_hash="abc",
        entries={"tests/alpha/test_a.py": split_tests._CacheEntry(hash="h1", count=5)},
    )
    cache.save(cache_path)
    loaded = split_tests._Cache.load(cache_path, "abc")
    assert loaded.entries == cache.entries
    assert loaded.invalidation_hash == "abc"


def test_cache_load_missing_returns_empty(tmp_path: Path) -> None:
    """A missing cache file degrades gracefully to an empty cache."""
    cache = split_tests._Cache.load(tmp_path / "missing.json", "abc")
    assert cache.entries == {}
    assert cache.invalidation_hash == "abc"


def test_cache_load_invalid_json_returns_empty(tmp_path: Path) -> None:
    """Corrupt JSON is treated as a cache miss instead of crashing."""
    path = tmp_path / "broken.json"
    path.write_text("{not json")
    cache = split_tests._Cache.load(path, "abc")
    assert cache.entries == {}


def test_cache_load_wrong_version_returns_empty(tmp_path: Path) -> None:
    """An older cache schema is discarded rather than misread."""
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"version": 0, "invalidation_hash": "abc", "files": {}}))
    cache = split_tests._Cache.load(path, "abc")
    assert cache.entries == {}


def test_cache_load_conftest_drift_returns_empty(tmp_path: Path) -> None:
    """A conftest change invalidates the entire cached set."""
    path = tmp_path / "cache.json"
    path.write_text(
        json.dumps(
            {
                "version": split_tests._CACHE_VERSION,
                "invalidation_hash": "old",
                "files": {"test_a.py": {"hash": "h1", "count": 3}},
            }
        )
    )
    cache = split_tests._Cache.load(path, "new")
    assert cache.entries == {}


def test_cache_load_drops_malformed_entries(tmp_path: Path) -> None:
    """Malformed per-file entries are skipped, valid ones are kept."""
    path = tmp_path / "cache.json"
    path.write_text(
        json.dumps(
            {
                "version": split_tests._CACHE_VERSION,
                "invalidation_hash": "abc",
                "files": {
                    "good.py": {"hash": "h1", "count": 3},
                    "bad_count.py": {"hash": "h2", "count": "three"},
                    "missing_hash.py": {"count": 4},
                    "not_dict.py": 5,
                },
            }
        )
    )
    cache = split_tests._Cache.load(path, "abc")
    assert set(cache.entries) == {"good.py"}


def test_resolve_from_cache_hits_and_misses(tree: Path) -> None:
    """Files with matching hashes are hits; edited or new files are misses."""
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    alpha_two = tree / "components" / "alpha" / "test_two.py"
    beta_x = tree / "components" / "beta" / "test_x.py"

    alpha_one_hash = split_tests._hash_file(alpha_one)
    cache = split_tests._Cache(
        invalidation_hash="dummy",
        entries={
            str(alpha_one.relative_to(tree)): split_tests._CacheEntry(
                hash=alpha_one_hash, count=1
            ),
            str(alpha_two.relative_to(tree)): split_tests._CacheEntry(
                hash="stale", count=99
            ),
        },
    )

    hits, missing = split_tests._resolve_from_cache(
        [alpha_one, alpha_two, beta_x], cache, tree
    )
    assert hits == {alpha_one: split_tests._CacheEntry(hash=alpha_one_hash, count=1)}
    assert set(missing) == {alpha_two, beta_x}


def test_collect_tests_warm_cache_skips_pytest(tree: Path) -> None:
    """A warm cache with no diffs should skip the pytest subprocess entirely."""
    cache_path = tree / "cache.json"
    alpha_one = tree / "components" / "alpha" / "test_one.py"
    alpha_two = tree / "components" / "alpha" / "test_two.py"
    beta_x = tree / "components" / "beta" / "test_x.py"
    split_tests._Cache(
        invalidation_hash=_invalidation_hash_for(tree),
        entries={
            str(alpha_one.relative_to(tree)): split_tests._CacheEntry(
                hash=split_tests._hash_file(alpha_one), count=1
            ),
            str(alpha_two.relative_to(tree)): split_tests._CacheEntry(
                hash=split_tests._hash_file(alpha_two), count=2
            ),
            str(beta_x.relative_to(tree)): split_tests._CacheEntry(
                hash=split_tests._hash_file(beta_x), count=3
            ),
        },
    ).save(cache_path)

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

    split_tests._Cache(
        invalidation_hash=_invalidation_hash_for(tree),
        entries={
            str(alpha_one.relative_to(tree)): split_tests._CacheEntry(
                hash=split_tests._hash_file(alpha_one), count=1
            ),
        },
    ).save(cache_path)

    def fake_run_batches(paths: list[Path]) -> list[tuple[str, str, int]]:
        # Re-collected files emit one fake test each so we can verify which
        # ones the batched runner was asked for.
        return [
            (
                "\n".join(f"{p}: 1" for p in paths) + "\n",
                "",
                0,
            )
        ]

    with patch.object(
        split_tests, "_run_collect_batches", side_effect=fake_run_batches
    ) as run_batches:
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
    split_tests._Cache(
        invalidation_hash=_invalidation_hash_for(tree),
        entries={
            str(alpha_one.relative_to(tree)): split_tests._CacheEntry(
                hash=split_tests._hash_file(alpha_one), count=1
            ),
        },
    ).save(cache_path)

    def fake_run_batches(paths: list[Path]) -> list[tuple[str, str, int]]:
        # Pretend pytest didn't see alpha_two at all.
        emitted = [p for p in paths if p != alpha_two]
        return [("\n".join(f"{p}: 1" for p in emitted) + "\n", "", 0)]

    with patch.object(
        split_tests, "_run_collect_batches", side_effect=fake_run_batches
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

    split_tests._Cache(
        invalidation_hash=_invalidation_hash_for(tree),
        entries={
            str(alpha_one.relative_to(tree)): split_tests._CacheEntry(
                hash=split_tests._hash_file(alpha_one), count=1
            ),
            ghost_rel: split_tests._CacheEntry(hash="dead", count=42),
        },
    ).save(cache_path)

    def fake_run_batches(paths: list[Path]) -> list[tuple[str, str, int]]:
        return [
            (
                "\n".join(f"{p}: 1" for p in paths) + "\n",
                "",
                0,
            )
        ]

    with patch.object(
        split_tests, "_run_collect_batches", side_effect=fake_run_batches
    ):
        split_tests.collect_tests(tree, cache_path)

    saved = json.loads(cache_path.read_text())
    assert ghost_rel not in saved["files"]
