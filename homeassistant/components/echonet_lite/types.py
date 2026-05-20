"""Shared types and data models for the HEMS Echonet Lite integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pyhems import DefinitionsRegistry, HemsClient, PropertyPoller

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from . import _RuntimeIssueMonitor
    from .coordinator import EchonetLiteCoordinator


@dataclass(slots=True)
class RuntimeHealth:
    """Health metadata tracked for the runtime client."""

    last_client_error: str | None = None
    last_client_error_at: float | None = None
    last_restart_at: float | None = None
    restart_attempts: int = 0


@dataclass(slots=True)
class EchonetLiteRuntimeData:
    """Runtime data stored on the config entry."""

    definitions: DefinitionsRegistry
    coordinator: EchonetLiteCoordinator
    client: HemsClient
    unsubscribe_runtime: Callable[[], None]
    property_poller: PropertyPoller
    issue_monitor: _RuntimeIssueMonitor
    health: RuntimeHealth
    discovery_task: asyncio.Task[Any]
    event_consumer_task: asyncio.Task[Any]


EchonetLiteConfigEntry = ConfigEntry[EchonetLiteRuntimeData]


__all__ = [
    "EchonetLiteConfigEntry",
    "EchonetLiteRuntimeData",
    "RuntimeHealth",
]
