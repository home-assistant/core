"""Models for Risco integration."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pyrisco import RiscoCloud, RiscoLocal
from pyrisco.cloud.alarm import Alarm
from pyrisco.cloud.event import Event

from homeassistant.config_entries import ConfigEntry

type RiscoConfigEntry = ConfigEntry[RiscoData]


@dataclass
class RiscoData:
    """Runtime data for the Risco integration."""

    local_data: LocalData | None = None
    cloud_data: CloudData | None = None


@dataclass
class CloudData:
    """A data class for cloud data passed to the platforms."""

    system: RiscoCloud
    alarm: Alarm
    events: list[Event] = field(default_factory=list)


@dataclass
class LocalData:
    """A data class for local data passed to the platforms."""

    system: RiscoLocal
    partition_updates: dict[int, Callable[[], Any]] = field(default_factory=dict)
