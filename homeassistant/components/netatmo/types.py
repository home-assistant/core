"""Types for the Netatmo integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .api import AsyncConfigEntryNetatmoAuth
from .data_handler import NetatmoDataHandler

type NetatmoConfigEntry = ConfigEntry[NetatmoData]


@dataclass
class NetatmoData:
    """Netatmo runtime data stored in config entry."""

    auth: AsyncConfigEntryNetatmoAuth
    data_handler: NetatmoDataHandler
