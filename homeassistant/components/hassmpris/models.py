"""The hassmpris integration models."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

import hassmpris_client

from .media_player_entity_manager import EntityManager


@dataclass
class HassmprisData:
    """Data for the hassmpris integration."""

    client: hassmpris_client.AsyncMPRISClient
    unloaders: list[Callable[[], Coroutine[Any, Any, None]]]
    unload_func: Callable[..., Coroutine[Any, Any, None]] | None
    entity_manager: EntityManager | None
