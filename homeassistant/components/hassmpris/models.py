"""The hassmpris integration models."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypedDict

import hassmpris_client

from .media_player import MPRISCoordinator


@dataclass
class HassmprisData:
    """Data for the hassmpris integration."""

    client: hassmpris_client.AsyncMPRISClient
    unloaders: list[Callable[[], Coroutine[Any, Any, None]]]
    unload_func: Callable[..., Coroutine[Any, Any, None]] | None
    entity_manager: MPRISCoordinator | None


class ConfigEntryData(TypedDict):
    """Configuration data stored in ConfigEntry."""

    unique_id: str
    host: str
    cakes_port: int
    mpris_port: int
