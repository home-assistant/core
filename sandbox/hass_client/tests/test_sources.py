"""Tests for the sandbox-side integration-source fetch (``hass_client.sources``).

All fetches use a local in-memory tarball fixture — no test hits the network.
"""

import asyncio
from collections.abc import Iterator
import io
from pathlib import Path
import tarfile

from hass_client import sources as sources_module
from hass_client._proto import sandbox_pb2 as pb
from hass_client.sources import SandboxSourceError, async_ensure_integration_source
import pytest


@pytest.fixture(autouse=True)
def _clear_fetch_state() -> Iterator[None]:
    """Reset the single-flight download state between tests for isolation."""
    sources_module._INFLIGHT.clear()  # noqa: SLF001
    sources_module._COMPLETED.clear()  # noqa: SLF001
    yield
    sources_module._INFLIGHT.clear()  # noqa: SLF001
    sources_module._COMPLETED.clear()  # noqa: SLF001


def _make_tarball(
    *, top: str, files: dict[str, str]
) -> bytes:
    """Build a gzipped tarball mimicking GitHub's codeload layout.

    ``files`` maps a path relative to ``top`` to its contents.
    """
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for rel, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name=f"{top}/{rel}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _git_source(domain: str = "my_custom") -> pb.IntegrationSource:
    return pb.IntegrationSource(
        kind="git",
        url="https://github.com/owner/my_custom",
        ref="a" * 40,
        tag="v1.0.0",
        domain=domain,
        subdir=f"custom_components/{domain}",
    )


async def test_builtin_is_a_noop(tmp_path: Path) -> None:
    """A builtin source fetches nothing and creates no files."""
    calls = 0

    async def _fetch(url: str, ref: str) -> bytes:
        nonlocal calls
        calls += 1
        return b""

    await async_ensure_integration_source(
        str(tmp_path), pb.IntegrationSource(kind="builtin"), fetch=_fetch
    )

    assert calls == 0
    assert not (tmp_path / "custom_components").exists()


async def test_unset_source_is_a_noop(tmp_path: Path) -> None:
    """An unset (default) source is treated as builtin — no fetch."""
    calls = 0

    async def _fetch(url: str, ref: str) -> bytes:
        nonlocal calls
        calls += 1
        return b""

    await async_ensure_integration_source(
        str(tmp_path), pb.IntegrationSource(), fetch=_fetch
    )

    assert calls == 0


async def test_git_source_extracts_into_config_dir(tmp_path: Path) -> None:
    """A git source extracts the repo subdir into custom_components/<domain>."""
    tarball = _make_tarball(
        top="my_custom-aaaa",
        files={
            "custom_components/my_custom/manifest.json": '{"domain": "my_custom"}',
            "custom_components/my_custom/__init__.py": "DOMAIN = 'my_custom'",
            "README.md": "ignored — outside the subdir",
        },
    )

    async def _fetch(url: str, ref: str) -> bytes:
        return tarball

    await async_ensure_integration_source(
        str(tmp_path), _git_source(), fetch=_fetch
    )

    dest = tmp_path / "custom_components" / "my_custom"
    assert (dest / "manifest.json").read_text() == '{"domain": "my_custom"}'
    assert (dest / "__init__.py").read_text() == "DOMAIN = 'my_custom'"
    # Files outside the subdir are not extracted.
    assert not (tmp_path / "README.md").exists()


async def test_concurrent_same_ref_shares_one_download(tmp_path: Path) -> None:
    """Concurrent entries from the same (url, ref) share one in-flight fetch."""
    tarball = _make_tarball(
        top="my_custom-aaaa",
        files={
            "custom_components/foo/manifest.json": "{}",
            "custom_components/bar/manifest.json": "{}",
        },
    )
    calls = 0

    async def _fetch(url: str, ref: str) -> bytes:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return tarball

    source_foo = pb.IntegrationSource(
        kind="git",
        url="https://github.com/owner/repo",
        ref="z" * 40,
        domain="foo",
        subdir="custom_components/foo",
    )
    source_bar = pb.IntegrationSource(
        kind="git",
        url="https://github.com/owner/repo",
        ref="z" * 40,
        domain="bar",
        subdir="custom_components/bar",
    )

    await asyncio.gather(
        async_ensure_integration_source(str(tmp_path), source_foo, fetch=_fetch),
        async_ensure_integration_source(str(tmp_path), source_bar, fetch=_fetch),
    )

    assert calls == 1
    assert (tmp_path / "custom_components" / "foo" / "manifest.json").exists()
    assert (tmp_path / "custom_components" / "bar" / "manifest.json").exists()


async def test_sequential_new_subdir_redownloads(tmp_path: Path) -> None:
    """A finished download is not pinned — a later new-subdir fetch re-downloads."""
    tarball = _make_tarball(
        top="my_custom-aaaa",
        files={
            "custom_components/foo/manifest.json": "{}",
            "custom_components/bar/manifest.json": "{}",
        },
    )
    calls = 0

    async def _fetch(url: str, ref: str) -> bytes:
        nonlocal calls
        calls += 1
        return tarball

    source_foo = pb.IntegrationSource(
        kind="git",
        url="https://github.com/owner/repo",
        ref="z" * 40,
        domain="foo",
        subdir="custom_components/foo",
    )
    source_bar = pb.IntegrationSource(
        kind="git",
        url="https://github.com/owner/repo",
        ref="z" * 40,
        domain="bar",
        subdir="custom_components/bar",
    )

    await async_ensure_integration_source(str(tmp_path), source_foo, fetch=_fetch)
    await async_ensure_integration_source(str(tmp_path), source_bar, fetch=_fetch)

    assert calls == 2
    assert (tmp_path / "custom_components" / "foo" / "manifest.json").exists()
    assert (tmp_path / "custom_components" / "bar" / "manifest.json").exists()


async def test_already_present_skips_fetch(tmp_path: Path) -> None:
    """An existing custom_components/<domain>/manifest.json skips the fetch."""
    dest = tmp_path / "custom_components" / "my_custom"
    dest.mkdir(parents=True)
    (dest / "manifest.json").write_text("{}")
    calls = 0

    async def _fetch(url: str, ref: str) -> bytes:
        nonlocal calls
        calls += 1
        return b""

    await async_ensure_integration_source(
        str(tmp_path), _git_source(), fetch=_fetch
    )

    assert calls == 0


async def test_missing_manifest_raises(tmp_path: Path) -> None:
    """A fetched tree without manifest.json is rejected."""
    tarball = _make_tarball(
        top="my_custom-aaaa",
        files={"custom_components/my_custom/__init__.py": "x = 1"},
    )

    async def _fetch(url: str, ref: str) -> bytes:
        return tarball

    with pytest.raises(SandboxSourceError, match="manifest.json"):
        await async_ensure_integration_source(
            str(tmp_path), _git_source(), fetch=_fetch
        )


async def test_unknown_kind_raises(tmp_path: Path) -> None:
    """An unrecognised source kind is an error."""

    async def _fetch(url: str, ref: str) -> bytes:
        return b""

    with pytest.raises(SandboxSourceError, match="unknown integration source kind"):
        await async_ensure_integration_source(
            str(tmp_path), pb.IntegrationSource(kind="svn"), fetch=_fetch
        )


async def test_empty_subdir_match_raises(tmp_path: Path) -> None:
    """A tarball with no files under the subdir is rejected."""
    tarball = _make_tarball(
        top="my_custom-aaaa",
        files={"some/other/path.py": "x = 1"},
    )

    async def _fetch(url: str, ref: str) -> bytes:
        return tarball

    with pytest.raises(SandboxSourceError):
        await async_ensure_integration_source(
            str(tmp_path), _git_source(), fetch=_fetch
        )
