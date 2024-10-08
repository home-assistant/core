"""Mealie util functions."""

from __future__ import annotations

from awesomeversion import AwesomeVersion


def create_version(version: str) -> AwesomeVersion:
    """Convert beta versions to PEP440."""
    return AwesomeVersion(version.replace("beta-", "b"))
