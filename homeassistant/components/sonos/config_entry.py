"""Module."""

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE

from .speaker import SonosSpeaker

if TYPE_CHECKING:
    from .alarms import SonosAlarms
    from .favorites import SonosFavorites


@dataclass
class UnjoinData:
    """Class to track data necessary for unjoin coalescing."""

    speakers: list[SonosSpeaker]
    event: asyncio.Event = field(default_factory=asyncio.Event)


@dataclass
class SonosData:
    """Storage class for platform global data."""

    discovered: OrderedDict[str, "SonosSpeaker"] = field(default_factory=OrderedDict)
    favorites: dict[str, "SonosFavorites"] = field(default_factory=dict)
    alarms: dict[str, "SonosAlarms"] = field(default_factory=dict)
    topology_condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    hosts_heartbeat: CALLBACK_TYPE | None = None
    discovery_known: set[str] = field(default_factory=set)
    boot_counts: dict[str, int] = field(default_factory=dict)
    mdns_names: dict[str, str] = field(default_factory=dict)
    entity_id_mappings: dict[str, "SonosSpeaker"] = field(default_factory=dict)
    unjoin_data: dict[str, "UnjoinData"] = field(default_factory=dict)


type SonosConfigEntry = ConfigEntry[SonosData]
