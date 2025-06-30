"""Type definitions for Z-Wave JS integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from zwave_js_server.const import LogLevel

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from zwave_js_server.client import Client as ZwaveClient

    from . import DriverEvents


@dataclass
class ZwaveJSData:
    """Data for zwave_js runtime data."""

    client: ZwaveClient
    driver_events: DriverEvents
    old_server_log_level: LogLevel | None = None


type ZwaveJSConfigEntry = ConfigEntry[ZwaveJSData]
