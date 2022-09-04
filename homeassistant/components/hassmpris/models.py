"""The hassmpris integration models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Coroutine, Any
from .media_player_entity_manager import EntityManager

import hassmpris_client


@dataclass
class HassmprisData:
    """Data for the hassmpris integration."""

    client: hassmpris_client.AsyncMPRISClient
    unloaders: list[Callable[[], Coroutine[Any, Any, None]]]
    unload_func: Callable[..., Coroutine[Any, Any, None]] | None
    entity_manager: EntityManager | None
