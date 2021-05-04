"""Rako shared models."""
from __future__ import annotations

from asyncio import Task
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from .bridge import RakoBridge
    from .light import RakoLight


class RakoDomainEntryData(TypedDict):
    """A single Rako config entry's data."""

    rako_bridge_client: RakoBridge
    rako_light_map: dict[str, RakoLight]
    rako_listener_task: Task | None
