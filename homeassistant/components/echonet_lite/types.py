"""Shared types and data models for the HEMS integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from pyhems import EOJ
from pyhems.definitions import DefinitionsRegistry
from pyhems.runtime import HemsClient

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


class PropertyPollerProtocol(Protocol):
    # pylint: disable=unnecessary-ellipsis
    """Protocol for property polling."""

    def stop(self) -> None:
        """Cancel listeners and scheduled callbacks."""
        ...

    def schedule_immediate_poll(self, device_key: str, *, delay: float = 1.0) -> None:
        """Schedule polling for a device earlier than the regular cadence."""
        ...


@dataclass(slots=True)
class EchonetLiteNodeState:
    """State for a discovered node (SEOJ)."""

    eoj: EOJ
    properties: dict[int, bytes]
    last_seen: float
    node_id: str
    manufacturer_code: int
    get_epcs: frozenset[int]
    set_epcs: frozenset[int]
    inf_epcs: frozenset[int]
    poll_epcs: frozenset[int]
    product_code: str | None
    serial_number: str | None

    @property
    def device_key(self) -> str:
        """Return the unique device key."""
        return f"{self.node_id}-{self.eoj:06x}"


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
    property_poller: PropertyPollerProtocol
    issue_monitor: RuntimeIssueMonitorProtocol
    health: RuntimeHealth
    discovery_task: asyncio.Task[Any]


EchonetLiteConfigEntry = ConfigEntry[EchonetLiteRuntimeData]


__all__ = [
    "EchonetLiteConfigEntry",
    "EchonetLiteNodeState",
    "EchonetLiteRuntimeData",
    "PropertyPollerProtocol",
    "RuntimeHealth",
    "RuntimeIssueMonitorProtocol",
]
