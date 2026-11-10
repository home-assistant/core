"""Util to decode content from the github API."""

from base64 import b64decode


def decode_content(content: str) -> str:
    """Decode content."""
    return b64decode(bytearray(content, "utf-8")).decode()
