"""Constants for the OpenDisplay integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from opendisplay import GlobalConfig

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from opendisplay.models import FirmwareVersion

DOMAIN = "opendisplay"


@dataclass
class OpenDisplayRuntimeData:
    """Runtime data for an OpenDisplay config entry."""

    firmware: FirmwareVersion
    device_config: GlobalConfig


type OpenDisplayConfigEntry = ConfigEntry[OpenDisplayRuntimeData]
