"""The bthome integration models."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BTHomeData:
    """Data for the bthome integration."""

    discovered_event_classes: set[str]
