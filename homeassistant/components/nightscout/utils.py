"""Nightscout util functions."""
from __future__ import annotations

import hashlib


def hash_from_url(url: str) -> str:
    """Hash url to create a unique ID."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()
