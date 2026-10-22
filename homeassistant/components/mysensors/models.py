"""Models for the MySensors integration."""

from asyncio import Task
from collections import defaultdict
from dataclasses import dataclass, field

from mysensors import BaseAsyncGateway

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from .const import DevId

type MySensorsConfigEntry = ConfigEntry[MySensorsData]


@dataclass
class MySensorsData:
    """Runtime data for a MySensors gateway."""

    gateway: BaseAsyncGateway
    discovered_nodes: set[int] = field(default_factory=set)
    discovered_dev_ids: defaultdict[Platform, set[DevId]] = field(
        default_factory=lambda: defaultdict(set)
    )
    gateway_start_task: Task[None] | None = None
