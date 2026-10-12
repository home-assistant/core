#!/usr/bin/env python3
# ruff: noqa: T201, D103, BLE001
"""Sync HACS default custom integrations (default branch HEAD, installed text files only).

Usage: python3 .claude/skills/custom-integration-sources/scripts/sync.py
    [--dest DIR] [--force] [--workers N] [REPO ...]

Commit SHAs are recorded in DIR/.state.json so only changed repos are downloaded.
Repos dropped from the HACS list are removed. Requires an authenticated `gh`.
"""

import argparse
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import BinaryIO
import urllib.error
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DEST = REPO_ROOT / ".custom_integration_sources"
HACS_LIST = "https://raw.githubusercontent.com/hacs/default/master/integration"
GRAPHQL = "https://api.github.com/graphql"
BATCH = 50
RETRIES = 4
CHUNK = 1 << 20
# Same binary heuristic as git: a NUL byte in the first 8000 bytes
BINARY_PROBE = 8000
# Characters GitHub allows in owner and repo names; slugs become paths under root
REPO_SLUG = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+")
LOCK_FILE = ".lock"
HACS_JSON_MAX = 1 << 16
# Exit status when the sync completed but some repos could not be downloaded
# (argparse already uses 2 for usage errors)
EXIT_PARTIAL = 3
MIN_LIST_RATIO = 0.5


def is_repo_slug(value: str) -> bool:
    """Return True for a plain owner/repo that cannot escape the destination."""
    return bool(REPO_SLUG.fullmatch(value)) and value.split("/")[1] not in {".", ".."}


def _repo_arg(value: str) -> str:
    if not is_repo_slug(value):
        raise argparse.ArgumentTypeError(f"not an owner/repo: {value!r}")
    return value


def _token() -> str:
    return subprocess.run(
        ["gh", "auth", "token"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _retry[T](func: Callable[[], T]) -> T:
    """Call func, retrying server errors and network failures with backoff."""
    for attempt in range(RETRIES):
        try:
            return func()
        except urllib.error.HTTPError as err:
            if err.code < 500 or attempt == RETRIES - 1:
                raise
        except OSError:
            if attempt == RETRIES - 1:
                raise
        time.sleep(2**attempt)
    raise AssertionError


def _get(url: str, token: str | None = None, data: bytes | None = None) -> bytes:
    req = urllib.request.Request(url, data=data)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"bearer {token}")

    def fetch() -> bytes:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()

    return _retry(fetch)


def _download_to(url: str, out: BinaryIO) -> None:
    """Stream url into out, restarting from scratch on each retry."""

    def fetch() -> None:
        out.seek(0)
        out.truncate()
        with urllib.request.urlopen(url, timeout=120) as resp:
            shutil.copyfileobj(resp, out, CHUNK)

    _retry(fetch)


def fetch_heads(repos: list[str], token: str) -> dict[str, str | None]:
    """Return default-branch HEAD SHA per repo (None if missing/empty)."""

    def query(chunk: list[str]) -> dict[str, str | None]:
        parts = []
        for n, repo in enumerate(chunk):
            owner, name = repo.split("/", 1)
            parts.append(
                f"r{n}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)})"
                " { defaultBranchRef { target { oid } } }"
            )
        payload = json.dumps({"query": "query {" + " ".join(parts) + "}"}).encode()
        body = json.loads(_get(GRAPHQL, token, payload))
        # Only per-repo NOT_FOUND is expected; anything else (rate limit, bad
        # query) must abort, or the prune step would delete every cached repo
        unexpected = [
            err
            for err in body.get("errors", [])
            if err.get("type") != "NOT_FOUND" or len(err.get("path", [])) != 1
        ]
        if unexpected or body.get("data") is None:
            raise RuntimeError(f"GraphQL query failed: {unexpected or body}")
        data = body["data"]
        result = {}
        for n, repo in enumerate(chunk):
            ref = (data.get(f"r{n}") or {}).get("defaultBranchRef")
            result[repo] = ref["target"]["oid"] if ref else None
        return result

    heads: dict[str, str | None] = {}
    chunks = [repos[i : i + BATCH] for i in range(0, len(repos), BATCH)]
    # Few workers: GraphQL secondary rate limits punish high concurrency
    with ThreadPoolExecutor(6) as pool:
        for chunk_heads in pool.map(query, chunks):
            heads.update(chunk_heads)
            print(f"  heads {len(heads)}/{len(repos)}", file=sys.stderr)
    return heads


def download(root: Path, repo: str, sha: str) -> None:
    """Replace root/repo with the filtered contents of the tarball at sha."""
    dest = root / repo
    tmp = dest.with_name(dest.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    # Spooled to disk, so memory stays flat whatever the archive or file sizes
    with tempfile.TemporaryFile(dir=root) as archive:
        _download_to(f"https://codeload.github.com/{repo}/tar.gz/{sha}", archive)
        archive.seek(0)
        _extract(archive, tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)


def _content_in_root(
    tar: tarfile.TarFile, files: list[tuple[tarfile.TarInfo, PurePosixPath]]
) -> bool:
    """Return the content_in_root flag from the root hacs.json, if any."""
    for member, rel in files:
        if rel == PurePosixPath("hacs.json"):
            fobj = tar.extractfile(member)
            try:
                manifest = json.loads(fobj.read(HACS_JSON_MAX)) if fobj else None
            except ValueError:
                return False
            return (
                isinstance(manifest, dict) and manifest.get("content_in_root") is True
            )
    return False


def _extract(archive: BinaryIO, tmp: Path) -> None:
    """Extract the installed text files of a repo tarball into tmp."""
    with tarfile.open(fileobj=archive, mode="r:gz") as tar:
        files = []
        for member in tar.getmembers():
            if not member.isfile():
                continue
            # Strip the "<repo>-<sha>/" prefix
            rel = PurePosixPath(*PurePosixPath(member.name).parts[1:])
            if rel.parts and ".." not in rel.parts and not rel.is_absolute():
                files.append((member, rel))
        # Keep what HACS installs: the whole repo for content_in_root, else
        # custom_components (whole repo too when there is none, as a fallback)
        keep_all = _content_in_root(tar, files) or not any(
            len(rel.parts) > 1 and rel.parts[0] == "custom_components"
            for _, rel in files
        )
        for member, rel in files:
            if (
                not keep_all
                and rel.parts[0] != "custom_components"
                and rel != PurePosixPath("hacs.json")
            ):
                continue
            fobj = tar.extractfile(member)
            if fobj is None:
                continue
            head = fobj.read(BINARY_PROBE)
            if b"\0" in head:
                continue
            target = tmp / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as out:
                out.write(head)
                shutil.copyfileobj(fobj, out, CHUNK)


def prune(root: Path, wanted: set[str]) -> list[str]:
    """Remove repo directories (and emptied owners) not in wanted."""
    removed = []
    for owner in root.iterdir():
        if not owner.is_dir() or owner.name.startswith("."):
            continue
        for repo_dir in owner.iterdir():
            repo = f"{owner.name}/{repo_dir.name}"
            if repo not in wanted:
                shutil.rmtree(repo_dir)
                removed.append(repo)
        if not any(owner.iterdir()):
            owner.rmdir()
    return removed


def load_state(root: Path) -> dict[str, str]:
    """Return the recorded SHAs, refusing a destination this script does not own.

    Pruning deletes every unknown <owner>/<repo> directory, so a populated
    directory without a valid state file must never be used.
    """
    state_file = root / ".state.json"
    if not any(path.name != LOCK_FILE for path in root.iterdir()):
        return {}
    try:
        state = json.loads(state_file.read_text())
    except OSError, ValueError:
        state = None
    if not isinstance(state, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in state.items()
    ):
        sys.exit(f"{root} is not empty and has no valid {state_file.name}; refusing")
    return state


def save_state(root: Path, state: dict[str, str]) -> None:
    """Write the state file atomically, so an interrupted run never truncates it."""
    tmp = root / ".state.json.tmp"
    tmp.write_text(json.dumps(state, indent=0, sort_keys=True))
    tmp.replace(root / ".state.json")


def lock(root: Path) -> BinaryIO:
    """Hold an exclusive lock on root for the life of the process."""
    fobj = (root / LOCK_FILE).open("ab")
    try:
        fcntl.flock(fobj, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(f"another sync is running on {root}")
    return fobj


def ensure_ignored(root: Path) -> None:
    """Add root to the local git exclude file if it is inside an unignored work tree."""

    def git(*cmd: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(root), *cmd],
            capture_output=True,
            text=True,
            check=False,
        )

    if git("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
        return
    if git("check-ignore", "-q", ".").returncode == 0:
        return
    top = Path(git("rev-parse", "--show-toplevel").stdout.strip())
    exclude = Path(git("rev-parse", "--git-path", "info/exclude").stdout.strip())
    if not exclude.is_absolute():
        exclude = root / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a") as fobj:
        fobj.write(f"/{root.relative_to(top).as_posix()}/\n")
    print(f"Added {root} to {exclude}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "repos", nargs="*", type=_repo_arg, help="only sync these owner/repo"
    )
    parser.add_argument("--force", action="store_true", help="ignore recorded SHAs")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    args = parser.parse_args()

    root: Path = args.dest.resolve()
    root.mkdir(parents=True, exist_ok=True)
    # Read-only ownership check first, so a refused directory is never modified
    load_state(root)
    # Kept open until exit; concurrent runs share the same temp paths
    _lock = lock(root)
    state = load_state(root)
    ensure_ignored(root)
    # Write it now so a run interrupted before any download still marks root
    save_state(root, state)

    hacs_list = json.loads(_get(HACS_LIST))
    if (
        not isinstance(hacs_list, list)
        or not hacs_list
        or not all(isinstance(repo, str) for repo in hacs_list)
    ):
        sys.exit("HACS list is not a non-empty list of strings; refusing")
    hacs = []
    for repo in sorted(set(hacs_list)):
        if is_repo_slug(repo):
            hacs.append(repo)
        else:
            print(f"skipping invalid HACS entry {repo!r}", file=sys.stderr)
    # A full sync prunes everything missing from the list, so a truncated
    # response must not be mistaken for repos leaving HACS
    if not args.repos and len(hacs) < len(state) * MIN_LIST_RATIO:
        sys.exit(
            f"HACS list has {len(hacs)} repos but {len(state)} are synced; refusing"
        )
    targets = args.repos or hacs
    print(f"HACS list: {len(hacs)} repos, checking {len(targets)}", file=sys.stderr)

    heads = fetch_heads(targets, _token())
    missing = sorted(r for r, sha in heads.items() if sha is None)
    todo = {
        r: sha
        for r, sha in heads.items()
        if sha and (args.force or state.get(r) != sha or not (root / r).is_dir())
    }
    print(f"{len(todo)} to download, {len(missing)} unavailable", file=sys.stderr)

    failed = []
    with ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(download, root, r, sha): r for r, sha in todo.items()}
        for done, fut in enumerate(as_completed(futures), 1):
            repo = futures[fut]
            try:
                fut.result()
            except Exception as err:
                failed.append(f"{repo}: {err}")
            else:
                state[repo] = todo[repo]
            if done % 100 == 0 or done == len(todo):
                print(f"  downloaded {done}/{len(todo)}", file=sys.stderr)
                save_state(root, state)

    removed: list[str] = []
    if not args.repos:
        wanted = set(hacs) - set(missing)
        removed = prune(root, wanted)
        state = {r: s for r, s in state.items() if r in wanted}
    else:
        for repo in missing:
            repo_dir = root / repo
            if repo_dir.is_dir():
                shutil.rmtree(repo_dir)
                removed.append(repo)
                if not any(repo_dir.parent.iterdir()):
                    repo_dir.parent.rmdir()
            state.pop(repo, None)
    save_state(root, state)

    print(f"updated {len(todo) - len(failed)}, removed {len(removed)}")
    for line in (*(f"unavailable {r}" for r in missing), *failed):
        print(line)
    if failed:
        print(f"{len(failed)} downloads failed; those repos are stale or missing")
        sys.exit(EXIT_PARTIAL)


if __name__ == "__main__":
    main()
