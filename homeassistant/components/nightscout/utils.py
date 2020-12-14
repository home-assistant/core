"""Nightscout util functions."""
import hashlib


def hash_from_url(url: str):
    """Hash url to create a unique ID."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()
