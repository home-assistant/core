#!/usr/bin/env python3
"""Sync HACS default custom integrations as partial git clones of default branch HEAD.

Usage: python3 -m script.sync_custom_integrations
    [--dest DIR] [--force] [--workers N] [REPO ...]

Each repo is a blobless clone (full history, file contents fetched on demand)
with a sparse checkout of what HACS installs. Commit SHAs are recorded in
DIR/.state.json so only changed repos are fetched.
Repos dropped from the HACS list are removed. Requires an authenticated `gh`.
"""

import argparse
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import BinaryIO
import urllib.error
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[1]
DEST_NAME = ".custom_integration_sources"
HACS_LIST = "https://raw.githubusercontent.com/hacs/default/master/integration"
GRAPHQL = "https://api.github.com/graphql"
BATCH = 50
RETRIES = 4
GIT_TIMEOUT = 600
# Inherited from an IDE terminal (VS Code sets GIT_ASKPASS), these would let
# git ask for credentials despite GIT_TERMINAL_PROMPT=0
ASKPASS_VARS = frozenset({"GIT_ASKPASS", "SSH_ASKPASS"})


def git_env(environ: Mapping[str, str]) -> dict[str, str]:
    """Return the environment for git commands on the copy.

    They run without user or system config: a repository's .gitattributes could
    otherwise select a filter defined there (such as an LFS or git-crypt smudge
    command), and templates or core.fsmonitor could run programs. Hooks are
    disabled outright. Proxies set in the environment still apply; clones are
    anonymous, so no credential helper is needed.
    """
    return {
        **{key: value for key, value in environ.items() if key not in ASKPASS_VARS},
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": os.devnull,
        # Never prompt for credentials (deleted or private repos) or pull LFS objects
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
    }


GIT_ENV = git_env(os.environ)
# Kept out of the checkout; sparse patterns filter by path, not by content
BINARY_GLOBS = (
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.ico",
    "*.bmp",
    "*.ttf",
    "*.otf",
    "*.woff",
    "*.woff2",
    "*.eot",
    "*.glb",
    "*.bin",
    "*.onnx",
    "*.tflite",
    "*.pt",
    "*.pkl",
    "*.npy",
    "*.bsp",
    "*.zip",
    "*.gz",
    "*.tgz",
    "*.tar",
    "*.7z",
    "*.whl",
    "*.pdf",
    "*.mp3",
    "*.mp4",
    "*.wav",
    "*.ogg",
    ".DS_Store",
    "*.wasm",
    "*.xcf",
    "*.so",
    "*.dll",
    "*.dylib",
    "*.exe",
    "*.pyc",
    "*.db",
    "*.sqlite",
)
# Characters GitHub allows in owner and repo names; slugs become paths under root
REPO_SLUG = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+")
LOCK_FILE = ".lock"
# Full error messages of the last sync, for the user (not for an AI session)
ERROR_LOG = ".sync-errors.log"
# Marks a state file as written by this script; anything else is not ours
STATE_FORMAT = "custom-integration-sources/1"
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


def default_dest() -> Path:
    """Return the copy in the main worktree, so all worktrees share one copy."""
    try:
        common_dir = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout.strip()
    except OSError, subprocess.SubprocessError:
        return REPO_ROOT / DEST_NAME
    return Path(common_dir).parent / DEST_NAME


def _positive_int(value: str) -> int:
    if not value.isdigit() or int(value) < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer: {value!r}")
    return int(value)


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


def fetch_heads(repos: list[str], token: str) -> dict[str, str | None]:
    """Return default-branch HEAD SHA per repo (None if missing, empty or private).

    Private repos count as unavailable: the token may still see one that went
    private, but the anonymous clone cannot fetch it.
    """

    def query(chunk: list[str]) -> dict[str, str | None]:
        parts = []
        for n, repo in enumerate(chunk):
            owner, name = repo.split("/", 1)
            parts.append(
                f"r{n}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)})"
                " { isPrivate defaultBranchRef { target { oid } } }"
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
            node = data.get(f"r{n}") or {}
            ref = None if node.get("isPrivate") else node.get("defaultBranchRef")
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


class GitError(RuntimeError):
    """A git command failed; stderr may quote third-party repository content."""

    def __init__(self, command: str, stderr: str) -> None:
        """Keep the command name apart from the untrusted stderr text."""
        super().__init__(f"git {command}: {stderr}")
        self.command = command


def _failure_kind(err: BaseException) -> str:
    """Describe a failure without any text that came from the repository."""
    if isinstance(err, GitError):
        return f"git {err.command} failed"
    if isinstance(err, subprocess.TimeoutExpired):
        return "timed out"
    return type(err).__name__


def _git(*args: str, cwd: Path | None = None) -> str:
    """Run git non-interactively, raising with the tail of stderr on failure."""
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=GIT_ENV,
        timeout=GIT_TIMEOUT,
        check=False,
    )
    if proc.returncode:
        raise GitError(args[0], proc.stderr.strip()[-300:])
    return proc.stdout


def _content_in_root(dest: Path, sha: str) -> bool:
    """Return the content_in_root flag from the root hacs.json at sha, if any.

    Trees are local in a blobless clone, so checking that the file exists needs
    no network; reading it may, and a failed read must fail the repo rather than
    quietly select the narrower checkout.
    """
    if not _git("ls-tree", "--name-only", sha, "hacs.json", cwd=dest).strip():
        return False
    try:
        manifest = json.loads(_git("show", f"{sha}:hacs.json", cwd=dest))
    except ValueError:
        return False
    return isinstance(manifest, dict) and manifest.get("content_in_root") is True


def _checkout(dest: Path, sha: str) -> None:
    """Check out what HACS installs at sha: custom_components, or the whole repo."""
    try:
        _git("cat-file", "-e", f"{sha}^{{commit}}", cwd=dest)
    except RuntimeError:
        _git("fetch", "--quiet", "--filter=blob:none", "origin", sha, cwd=dest)
    # Whole repo too when there is no custom_components, as a fallback
    whole = _content_in_root(dest, sha) or not _git(
        "ls-tree", "-d", "--name-only", sha, "custom_components", cwd=dest
    )
    patterns = ["/*"] if whole else ["/custom_components/", "/hacs.json"]
    patterns += [f"!{glob}" for glob in BINARY_GLOBS]
    patterns += [f"!{glob.upper()}" for glob in BINARY_GLOBS]
    # Symlinks become plain files holding the target path, so nothing in the
    # copy can resolve to a file outside it (such as local credentials)
    _git("config", "core.symlinks", "false", cwd=dest)
    _git("sparse-checkout", "set", "--no-cone", *patterns, cwd=dest)
    _git("reset", "--quiet", "--hard", sha, cwd=dest)
    _replace_symlinks(dest)


def _replace_symlinks(dest: Path) -> None:
    """Rewrite symlinks left by a checkout made before core.symlinks was off."""
    links = []
    for dirpath, dirnames, filenames in os.walk(dest):
        if Path(dirpath) == dest:
            dirnames[:] = [name for name in dirnames if name != ".git"]
        links.extend(
            Path(dirpath, name).relative_to(dest).as_posix()
            for name in dirnames + filenames
            if Path(dirpath, name).is_symlink()
        )
    if not links:
        return
    for link in links:
        (dest / link).unlink()
    _git("checkout", "--", *links, cwd=dest)


class UnsafePathError(RuntimeError):
    """A repo's owner or repo directory in the copy is a symlink."""


def _is_symlinked(root: Path, repo: str) -> bool:
    """Return True if the owner or repo directory of repo is a symlink.

    Nothing in a repository can create one at that level, but anything else on
    the machine can; following it would update or delete files outside the copy.
    """
    return (root / repo).parent.is_symlink() or (root / repo).is_symlink()


def download(root: Path, repo: str, sha: str) -> None:
    """Bring root/repo to sha, updating the clone in place or cloning afresh."""
    if _is_symlinked(root, repo):
        raise UnsafePathError(repo)
    dest = root / repo
    if (dest / ".git").is_dir():
        try:
            _checkout(dest, sha)
        except RuntimeError, subprocess.TimeoutExpired:
            pass  # Broken or interrupted clone: replace it below
        else:
            return
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Hidden and uniquely named: searches skip it and no repo name can clash
    tmp = Path(tempfile.mkdtemp(prefix=f".{dest.name}.", dir=dest.parent))
    try:
        _git(
            "clone",
            "--quiet",
            "--template=",
            "--config",
            "core.symlinks=false",
            "--filter=blob:none",
            "--no-checkout",
            f"https://github.com/{repo}.git",
            str(tmp),
        )
        _checkout(tmp, sha)
        shutil.rmtree(dest, ignore_errors=True)
        tmp.rename(dest)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def prune(root: Path, wanted: set[str]) -> list[str]:
    """Remove repo directories (and emptied owners) not in wanted.

    Files and symlinks (such as a .DS_Store left by a file manager) are never
    repos, so they are skipped rather than passed to rmtree.
    """
    removed = []
    for owner in root.iterdir():
        if owner.is_symlink() or not owner.is_dir() or owner.name.startswith("."):
            continue
        for repo_dir in owner.iterdir():
            if repo_dir.is_symlink() or not repo_dir.is_dir():
                continue
            repo = f"{owner.name}/{repo_dir.name}"
            if repo not in wanted:
                shutil.rmtree(repo_dir)
                removed.append(repo)
        if not any(owner.iterdir()):
            owner.rmdir()
    return removed


def load_state(root: Path) -> tuple[dict[str, str], str | None]:
    """Return the recorded SHAs and synced_at, refusing a destination not ours.

    Pruning deletes every unknown <owner>/<repo> directory, so a populated
    directory without a valid state file must never be used.
    """
    state_file = root / ".state.json"
    if not any(path.name != LOCK_FILE for path in root.iterdir()):
        return {}, None
    try:
        data = json.loads(state_file.read_text())
    except OSError, ValueError:
        data = None
    repos = data.get("repos") if isinstance(data, dict) else None
    synced_at = data.get("synced_at") if isinstance(data, dict) else None
    if (
        not isinstance(data, dict)
        or data.get("format") != STATE_FORMAT
        or not isinstance(repos, dict)
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in repos.items())
        or not isinstance(synced_at, str | None)
    ):
        sys.exit(f"{root} is not empty and has no valid {state_file.name}; refusing")
    return repos, synced_at


def save_state(root: Path, state: dict[str, str], synced_at: str | None) -> None:
    """Write the state file atomically, so an interrupted run never truncates it.

    synced_at is when the last full sync without failures finished; any other
    run keeps the previous value, so it reflects how fresh the whole copy is.
    """
    tmp = root / ".state.json.tmp"
    data: dict[str, object] = {"format": STATE_FORMAT, "repos": state}
    if synced_at is not None:
        data["synced_at"] = synced_at
    tmp.write_text(json.dumps(data, indent=0, sort_keys=True))
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
    """Add root to the local git exclude file if it is inside an unignored work tree.

    The default location is already in .gitignore; this covers a --dest inside
    a checkout.
    """

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
    rel = root.relative_to(top).as_posix()
    if "\n" in rel or "\r" in rel:
        sys.exit(f"{root!r} contains a line break; choose another --dest")
    exclude = Path(git("rev-parse", "--git-path", "info/exclude").stdout.strip())
    if not exclude.is_absolute():
        exclude = root / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    # Anchored at both ends, so only pattern characters need escaping; start
    # on a new line if the file does not end with one
    rule = "/" + re.sub(r"([\\*?\[])", r"\\\1", rel) + "/\n"
    existing = exclude.read_bytes() if exclude.exists() else b""
    with exclude.open("a") as fobj:
        fobj.write(rule if not existing or existing.endswith(b"\n") else "\n" + rule)
    print(f"Added {root} to {exclude}", file=sys.stderr)


def main() -> None:
    """Sync the destination with the HACS default integration list."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "repos", nargs="*", type=_repo_arg, help="only sync these owner/repo"
    )
    parser.add_argument("--force", action="store_true", help="ignore recorded SHAs")
    parser.add_argument("--workers", type=_positive_int, default=16)
    parser.add_argument(
        "--dest",
        type=Path,
        help=f"copy location (default: {DEST_NAME}/ in the main worktree)",
    )
    args = parser.parse_args()

    root: Path = (args.dest or default_dest()).resolve()
    root.mkdir(parents=True, exist_ok=True)
    # Read-only ownership check first, so a refused directory is never modified
    load_state(root)
    # Kept open until exit; concurrent runs share the same temp paths
    _lock = lock(root)
    state, synced_at = load_state(root)
    ensure_ignored(root)
    # Write it now so a run interrupted before any download still marks root
    save_state(root, state, synced_at)

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
        # No .git also covers copies made by the earlier tarball-based version;
        # a symlinked path always goes to download(), which rejects it
        if sha
        and (
            args.force
            or state.get(r) != sha
            or _is_symlinked(root, r)
            or not (root / r / ".git").is_dir()
        )
    }
    print(f"{len(todo)} to download, {len(missing)} unavailable", file=sys.stderr)

    # Forget the SHAs of repos about to change: checkouts are updated in place,
    # so an interrupted run must leave them unrecorded (and redone next time)
    # rather than paired with a SHA their files no longer match
    for repo in todo:
        state.pop(repo, None)
    save_state(root, state, synced_at)

    failed = []
    errors = []
    with ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(download, root, r, sha): r for r, sha in todo.items()}
        for done, fut in enumerate(as_completed(futures), 1):
            repo = futures[fut]
            try:
                fut.result()
            except Exception as err:  # noqa: BLE001
                # Full errors can quote repository content (such as file names),
                # so they go to a log for the user; the output only gets a kind
                failed.append(f"{repo}: {_failure_kind(err)}")
                errors.append(f"{repo}: {' '.join(str(err).split())}")
            else:
                state[repo] = todo[repo]
            if done % 100 == 0 or done == len(todo):
                print(f"  downloaded {done}/{len(todo)}", file=sys.stderr)
                save_state(root, state, synced_at)

    removed: list[str] = []
    if not args.repos:
        wanted = set(hacs) - set(missing)
        removed = prune(root, wanted)
        state = {r: s for r, s in state.items() if r in wanted}
    else:
        for repo in missing:
            repo_dir = root / repo
            if not _is_symlinked(root, repo) and repo_dir.is_dir():
                shutil.rmtree(repo_dir)
                removed.append(repo)
                if not any(repo_dir.parent.iterdir()):
                    repo_dir.parent.rmdir()
            state.pop(repo, None)
    if not args.repos and not failed:
        synced_at = datetime.now(UTC).isoformat(timespec="seconds")
    save_state(root, state, synced_at)

    error_log = root / ERROR_LOG
    if errors:
        error_log.write_text("\n".join(errors) + "\n")
    else:
        error_log.unlink(missing_ok=True)
    # Per-repo lines first, so the summary is always the last line of output
    for repo in missing:
        print(f"unavailable {repo}")
    for line in failed:
        print(f"failed {line}")
    summary = (
        f"updated {len(todo) - len(failed)}, removed {len(removed)},"
        f" unavailable {len(missing)}, failed {len(failed)}"
    )
    if failed:
        print(
            f"{summary}; {len(failed)} downloads failed, those repos are stale or missing"
        )
        sys.exit(EXIT_PARTIAL)
    print(summary)


if __name__ == "__main__":
    main()
