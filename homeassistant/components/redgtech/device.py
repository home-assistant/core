"""Device representation for Redgtech integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RedgtechDevice:
    """Representation of a Redgtech device."""

    unique_id: str
    name: str
    type: str
    state: bool
