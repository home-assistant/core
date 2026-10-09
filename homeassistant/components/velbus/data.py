"""Velbus integration runtime data types."""

import asyncio
from dataclasses import dataclass

from velbusaio.controller import Velbus

from homeassistant.config_entries import ConfigEntry


@dataclass
class VelbusData:
    """Runtime data for the Velbus config entry."""

    controller: Velbus
    scan_task: asyncio.Task


type VelbusConfigEntry = ConfigEntry[VelbusData]
