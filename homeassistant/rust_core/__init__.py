"""High-performance Rust-based core functions for Home Assistant.

This module provides optimized implementations of performance-critical
operations. It gracefully falls back to Python implementations if the
Rust extension is not available.
"""

from __future__ import annotations

from collections.abc import Mapping
import functools
import re
from typing import Any

# Try to import the Rust extension
try:
    from .rust_core import (
        fast_attributes_equal as _rust_fast_attributes_equal,
        split_entity_id as _rust_split_entity_id,
        valid_domain as _rust_valid_domain,
        valid_entity_id as _rust_valid_entity_id,
    )

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    _rust_valid_entity_id = None
    _rust_valid_domain = None
    _rust_split_entity_id = None
    _rust_fast_attributes_equal = None


# Original Python implementations for fallback
# Match the patterns from homeassistant/core.py
_OBJECT_ID = r"(?!_)[\da-z_]+(?<!_)"
_DOMAIN = r"(?!.+__)" + _OBJECT_ID
VALID_DOMAIN = re.compile(r"^" + _DOMAIN + r"$")
VALID_ENTITY_ID = re.compile(r"^" + _DOMAIN + r"\." + _OBJECT_ID + r"$")


@functools.lru_cache(512)
def _python_valid_domain(domain: str) -> bool:
    """Python fallback for domain validation."""
    return VALID_DOMAIN.match(domain) is not None


@functools.lru_cache(16384)  # MAX_EXPECTED_ENTITY_IDS
def _python_valid_entity_id(entity_id: str) -> bool:
    """Python fallback for entity ID validation."""
    return VALID_ENTITY_ID.match(entity_id) is not None


@functools.lru_cache(16384)  # MAX_EXPECTED_ENTITY_IDS
def _python_split_entity_id(entity_id: str) -> tuple[str, str]:
    """Python fallback for entity ID splitting."""
    domain, _, object_id = entity_id.partition(".")
    if not domain or not object_id:
        raise ValueError(f"Invalid entity ID {entity_id}")
    return domain, object_id


def _python_fast_attributes_equal(
    dict1: Mapping[str, Any], dict2: Mapping[str, Any]
) -> bool:
    """Python fallback for attribute comparison."""
    return dict1 == dict2


# Export the best available implementation
if RUST_AVAILABLE:
    valid_entity_id = _rust_valid_entity_id
    valid_domain = _rust_valid_domain
    split_entity_id = _rust_split_entity_id
    fast_attributes_equal = _rust_fast_attributes_equal
else:
    valid_entity_id = _python_valid_entity_id
    valid_domain = _python_valid_domain
    split_entity_id = _python_split_entity_id
    fast_attributes_equal = _python_fast_attributes_equal


__all__ = [
    "RUST_AVAILABLE",
    "fast_attributes_equal",
    "split_entity_id",
    "valid_domain",
    "valid_entity_id",
]
