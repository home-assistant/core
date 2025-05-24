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


class SonosData:
    """Storage class for platform global data."""

    def __init__(self) -> None:
        """Initialize the data."""
        # OrderedDict behavior used by SonosAlarms and SonosFavorites
        self.discovered: OrderedDict[str, SonosSpeaker] = OrderedDict()
        self.favorites: dict[str, SonosFavorites] = {}
        self.alarms: dict[str, SonosAlarms] = {}
        self.topology_condition = asyncio.Condition()
        self.hosts_heartbeat: CALLBACK_TYPE | None = None
        self.discovery_known: set[str] = set()
        self.boot_counts: dict[str, int] = {}
        self.mdns_names: dict[str, str] = {}
        self.entity_id_mappings: dict[str, SonosSpeaker] = {}
        self.unjoin_data: dict[str, UnjoinData] = {}


@dataclass
class SonosRuntimeData:
    """Data."""

    sonos_data: SonosData


type SonosConfigEntry = ConfigEntry[SonosRuntimeData]
