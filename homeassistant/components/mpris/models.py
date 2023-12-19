"""The MPRIS integration models."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypedDict

import hassmpris_client


@dataclass
class MPRISData:
    """Data for the MPRIS integration."""

    client: hassmpris_client.AsyncMPRISClient
    unloaders: list[Callable[[], Coroutine[Any, Any, None]]]


class ConfigEntryData(TypedDict):
    """Configuration data stored in ConfigEntry."""

    unique_id: str
    host: str
    cakes_port: int
    mpris_port: int
