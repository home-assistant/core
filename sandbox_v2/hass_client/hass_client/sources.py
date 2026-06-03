"""Sandbox-side integration-source fetching — fetch custom code at startup.

A stateless sandbox starts with only the bundled ``homeassistant`` package on
disk. Built-in integrations are already present (no-op); custom (HACS)
integrations carry a git :class:`~._proto.sandbox_v2_pb2.IntegrationSource`
descriptor on ``entry_setup`` that the sandbox fetches into
``<config>/custom_components/<domain>`` *before* ``async_setup`` runs (see
:meth:`hass_client.entry_runner.EntryRunner._handle_entry_setup`).

The fetch uses GitHub's codeload tarball for the exact commit sha (no ``git``
binary dependency, matching HACS). A process-lifetime cache keyed by
``(url, ref)`` means multiple entries sourced from the same repo download once.

The download primitive is injectable so tests substitute a local fixture for
the real network fetch — no test ever hits GitHub.
"""

import asyncio
from collections.abc import Awaitable, Callable
import io
import logging
from pathlib import Path
import tarfile

from ._proto import sandbox_v2_pb2 as pb

_LOGGER = logging.getLogger(__name__)

# url, ref -> downloaded tarball bytes. Process-lifetime only (honours
# "stateless": nothing survives a process restart). Guarded by _CACHE_LOCK so
# concurrent entries from the same repo download exactly once.
_TARBALL_CACHE: dict[tuple[str, str], bytes] = {}
_CACHE_LOCK = asyncio.Lock()

# (repo url, exact sha) -> tarball bytes.
FetchPrimitive = Callable[[str, str], Awaitable[bytes]]


class SandboxSourceError(Exception):
    """Raised when a custom integration's source cannot be fetched."""


async def async_ensure_integration_source(
    config_dir: str,
    source: pb.IntegrationSource,
    *,
    fetch: FetchPrimitive | None = None,
) -> None:
    """Ensure ``source``'s integration code is present under ``config_dir``.

    * ``builtin`` (or an unset source) → no-op; the bundled ``homeassistant``
      package provides built-ins.
    * ``git`` → if ``<config_dir>/custom_components/<domain>`` is not already
      present, download the tarball for the exact ``ref`` and extract the
      repo's ``subdir`` into it.

    ``fetch`` is the download primitive ``(url, ref) -> tarball bytes``;
    defaults to the real codeload download. Tests pass a local stub.
    """
    kind = source.kind or "builtin"
    if kind == "builtin":
        return
    if kind != "git":
        raise SandboxSourceError(f"unknown integration source kind {kind!r}")

    domain = source.domain
    if not domain:
        raise SandboxSourceError("git integration source is missing a domain")
    if not source.url or not source.ref:
        raise SandboxSourceError(
            f"git integration source for {domain!r} is missing url/ref"
        )

    dest = Path(config_dir) / "custom_components" / domain
    manifest = dest / "manifest.json"
    if manifest.exists():
        # Already fetched into this config dir (another entry of the same
        # domain, or a prior call) — nothing to do.
        return

    subdir = source.subdir or f"custom_components/{domain}"
    fetcher = fetch if fetch is not None else _default_fetch
    key = (source.url, source.ref)

    async with _CACHE_LOCK:
        tarball = _TARBALL_CACHE.get(key)
        if tarball is None:
            _LOGGER.info(
                "sandbox: fetching %s from %s@%s (%s)",
                domain,
                source.url,
                source.ref,
                source.tag or "no tag",
            )
            tarball = await fetcher(source.url, source.ref)
            _TARBALL_CACHE[key] = tarball

    await asyncio.get_running_loop().run_in_executor(
        None, _extract_subdir, tarball, subdir, dest
    )

    if not manifest.exists():
        raise SandboxSourceError(
            f"fetched source for {domain!r} has no manifest.json at "
            f"{subdir!r} (ref {source.ref})"
        )


def _extract_subdir(tarball: bytes, subdir: str, dest: Path) -> None:
    """Extract ``<top>/<subdir>/`` from a gzipped tarball into ``dest``.

    GitHub's codeload tarball wraps everything in a single top-level
    ``<repo>-<ref>/`` directory; the integration lives at ``<top>/<subdir>``.
    Members outside the subdir are ignored; any member resolving outside
    ``dest`` (path traversal) is rejected.
    """
    subdir = subdir.strip("/")
    dest_root = dest.resolve()
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tar:
        members = tar.getmembers()
        if not members:
            raise SandboxSourceError("fetched tarball is empty")
        top = members[0].name.split("/", 1)[0]
        prefix = f"{top}/{subdir}/"
        extracted = 0
        for member in members:
            if not member.name.startswith(prefix):
                continue
            rel = member.name[len(prefix) :]
            if not rel:
                continue
            target = (dest / rel).resolve()
            if not target.is_relative_to(dest_root):
                raise SandboxSourceError(
                    f"refusing path-traversal member {member.name!r}"
                )
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                # Skip symlinks / devices / etc. — integration trees are
                # plain files; anything else is suspect.
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            if source is None:
                continue
            with source, target.open("wb") as handle:
                handle.write(source.read())
            extracted += 1
        if extracted == 0:
            raise SandboxSourceError(
                f"fetched tarball had no files under {prefix!r}"
            )


def _codeload_url(url: str, ref: str) -> str:
    """Build the GitHub codeload tarball URL for ``url`` at ``ref``.

    ``https://github.com/owner/repo`` → ``https://codeload.github.com/owner/
    repo/tar.gz/<ref>``.
    """
    trimmed = url.rstrip("/").removesuffix(".git")
    parts = trimmed.split("/")
    if len(parts) < 2:
        raise SandboxSourceError(f"cannot derive owner/repo from url {url!r}")
    owner, repo = parts[-2], parts[-1]
    return f"https://codeload.github.com/{owner}/{repo}/tar.gz/{ref}"


async def _default_fetch(url: str, ref: str) -> bytes:
    """Download the codeload tarball for ``url`` at the exact ``ref`` (sha).

    The real network path. A one-shot transient session is fine here: this
    runs once per ``(url, ref)`` at sandbox startup. Imported lazily so the
    module (and tests using a stub) never require ``aiohttp``.
    """
    import aiohttp  # noqa: PLC0415 — keep aiohttp optional for the stubbed path

    tar_url = _codeload_url(url, ref)
    async with (
        aiohttp.ClientSession() as session,
        session.get(tar_url) as response,
    ):
        response.raise_for_status()
        return await response.read()


__all__ = [
    "FetchPrimitive",
    "SandboxSourceError",
    "async_ensure_integration_source",
]
