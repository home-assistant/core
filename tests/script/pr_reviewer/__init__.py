"""Tests for the PR reviewer workflow scripts."""

from dataclasses import dataclass
import json
import subprocess
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytest


@dataclass
class Reply:
    """A canned answer of `gh api`."""

    stdout: bytes = b""
    stderr: bytes = b""
    returncode: int = 0


def json_reply(data: Any) -> Reply:
    """Return a reply with JSON data."""
    return Reply(json.dumps(data).encode())


def error_reply(stderr: str) -> Reply:
    """Return a failed reply."""
    return Reply(stderr=stderr.encode(), returncode=1)


class FakeGh:
    """Stand in for `subprocess.run` of `gh api`, answering on the API path.

    Paths are relative to the repository, without the `per_page` parameter.
    """

    def __init__(self, repo: str) -> None:
        """Initialize the fake for a repository."""
        self._prefix = f"repos/{repo}/"
        self._replies: dict[str, list[Reply]] = {}

    def reply(self, path: str, *replies: Reply) -> None:
        """Answer requests for a path with the replies in turn, repeating the last."""
        self._replies[path] = list(replies)

    def json(self, path: str, *data: Any) -> None:
        """Answer requests for a path with JSON data in turn, repeating the last."""
        self.reply(path, *map(json_reply, data))

    def error(self, path: str, stderr: str) -> None:
        """Fail requests for a path."""
        self.reply(path, error_reply(stderr))

    def __call__(
        self, args: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[Any]:
        """Answer a `gh api` request."""
        assert args[:2] == ["gh", "api"]
        url = urlsplit(
            next(
                arg for arg in args[2:] if arg == "graphql" or arg.startswith("repos/")
            ).removeprefix(self._prefix)
        )
        query = urlencode([(k, v) for k, v in parse_qsl(url.query) if k != "per_page"])
        path = urlunsplit(url._replace(query=query))
        if path not in self._replies:
            pytest.fail(f"Unexpected gh request: {args}")
        replies = self._replies[path]
        reply = replies.pop(0) if len(replies) > 1 else replies[0]
        stdout: bytes | str = reply.stdout
        stderr: bytes | str = reply.stderr
        if kwargs.get("encoding"):
            stdout = reply.stdout.decode()
            stderr = reply.stderr.decode()
        if kwargs.get("check") and reply.returncode:
            raise subprocess.CalledProcessError(reply.returncode, args, stdout, stderr)
        return subprocess.CompletedProcess(args, reply.returncode, stdout, stderr)
