"""Helper classes and type definitions for SystemNexa2 integration.

This module provides:
- SystemNexa2ConfigEntry: type alias for config entries with runtime data;
- NexaSystem2RuntimeData: dataclass for storing runtime data.
"""

from dataclasses import dataclass, field

from sn2.device import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

type SystemNexa2ConfigEntry = ConfigEntry[NexaSystem2RuntimeData]


@dataclass
class NexaSystem2RuntimeData:
    """Storage runtime data for nexasystem2 config entries."""

    device: Device
    device_info: DeviceInfo
    main_entry: Entity | None = None
    config_entries: list[Entity] = field(default_factory=list)
