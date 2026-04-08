"""Models for Risco integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pyrisco import RiscoLocal

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import (
        RiscoDataUpdateCoordinator,
        RiscoEventsDataUpdateCoordinator,
    )

type RiscoConfigEntry = ConfigEntry[LocalData | CloudData]


@dataclass
class CloudData:
    """A data class for cloud data passed to the platforms."""

    coordinator: RiscoDataUpdateCoordinator
    events_coordinator: RiscoEventsDataUpdateCoordinator


@dataclass
class LocalData:
    """A data class for local data passed to the platforms."""

    system: RiscoLocal
    partition_updates: dict[int, Callable[[], Any]] = field(default_factory=dict)
