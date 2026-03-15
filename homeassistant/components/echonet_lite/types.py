"""Shared types and data models for the HEMS integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from pyhems import DefinitionsRegistry, HemsClient, PropertyPoller

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import EchonetLiteCoordinator


class RuntimeIssueMonitorProtocol(Protocol):
    # pylint: disable=unnecessary-ellipsis
    """Protocol for runtime issue monitoring."""

    def start(self) -> None:
        """Begin checking for runtime inactivity."""
        ...

    def stop(self) -> None:
        """Stop monitoring and clear any active issue."""
        ...

    def record_activity(self, timestamp: float) -> None:
        """Note that activity was observed and clear issues if present."""
        ...

    def record_client_error(self, message: str) -> None:
        """Create a repair issue describing the runtime client failure."""
        ...

    def clear_client_error(self) -> None:
        """Clear any existing runtime client error issue."""
        ...


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

    interface: str
    definitions: DefinitionsRegistry
    coordinator: EchonetLiteCoordinator
    client: HemsClient
    unsubscribe_runtime: Callable[[], None]
    property_poller: PropertyPoller
    issue_monitor: RuntimeIssueMonitorProtocol
    health: RuntimeHealth
    discovery_task: asyncio.Task[Any]


EchonetLiteConfigEntry = ConfigEntry[EchonetLiteRuntimeData]


__all__ = [
    "EchonetLiteConfigEntry",
    "EchonetLiteRuntimeData",
    "RuntimeHealth",
    "RuntimeIssueMonitorProtocol",
]
