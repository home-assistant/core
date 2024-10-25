"""Provide integration helpers that are aware of the mass integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from music_assistant.client import MusicAssistantClient


@dataclass
class MusicAssistantEntryData:
    """Hold Mass data for the config entry."""

    mass: MusicAssistantClient
    listen_task: asyncio.Task
