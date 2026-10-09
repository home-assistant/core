#!/usr/bin/env python3
# ruff: noqa: T201, D103, BLE001
"""Sync HACS default custom integrations (default branch HEAD, *.py + manifest.json only).

Usage: python3 .claude/skills/custom-integration-sources/scripts/sync.py
    [--dest DIR] [--force] [--workers N] [REPO ...]

Commit SHAs are recorded in DIR/.state.json so only changed repos are downloaded.
Repos dropped from the HACS list are removed. Requires an authenticated `gh`.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DEST = REPO_ROOT / ".custom_integration_sources"
HACS_LIST = "https://raw.githubusercontent.com/hacs/default/master/integration"
GRAPHQL = "https://api.github.com/graphql"
KEEP_SUFFIXES = {".py"}
KEEP_NAMES = {"manifest.json"}
BATCH = 50
RETRIES = 4


def _token() -> str:
    return subprocess.run(
        ["gh", "auth", "token"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _get(url: str, token: str | None = None, data: bytes | None = None) -> bytes:
    req = urllib.request.Request(url, data=data)
    if token:
        req.add_header("Authorization", f"bearer {token}")
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except urllib.error.HTTPError as err:
            if err.code < 500 or attempt == RETRIES - 1:
                raise
        except OSError:
            if attempt == RETRIES - 1:
                raise
        time.sleep(2**attempt)
    raise AssertionError


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
        data = json.loads(_get(GRAPHQL, token, payload)).get("data") or {}
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
    raw = _get(f"https://codeload.github.com/{repo}/tar.gz/{sha}")
    dest = root / repo
    tmp = dest.with_name(dest.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            # Strip the "<repo>-<sha>/" prefix
            rel = PurePosixPath(*PurePosixPath(member.name).parts[1:])
            if not rel.parts or ".." in rel.parts or rel.is_absolute():
                continue
            if rel.suffix not in KEEP_SUFFIXES and rel.name not in KEEP_NAMES:
                continue
            target = tmp / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            fobj = tar.extractfile(member)
            if fobj is not None:
                target.write_bytes(fobj.read())
    tmp.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)


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
    parser.add_argument("repos", nargs="*", help="only sync these owner/repo")
    parser.add_argument("--force", action="store_true", help="ignore recorded SHAs")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    args = parser.parse_args()

    root: Path = args.dest.resolve()
    root.mkdir(parents=True, exist_ok=True)
    ensure_ignored(root)
    state_file = root / ".state.json"

    state: dict[str, str] = (
        json.loads(state_file.read_text()) if state_file.exists() else {}
    )
    hacs = sorted(set(json.loads(_get(HACS_LIST))))
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
                state_file.write_text(json.dumps(state, indent=0, sort_keys=True))

    removed: list[str] = []
    if not args.repos:
        wanted = set(hacs) - set(missing)
        removed = prune(root, wanted)
        state = {r: s for r, s in state.items() if r in wanted}
    state_file.write_text(json.dumps(state, indent=0, sort_keys=True))

    print(f"updated {len(todo) - len(failed)}, removed {len(removed)}")
    for line in (*(f"unavailable {r}" for r in missing), *failed):
        print(line)


if __name__ == "__main__":
    main()
