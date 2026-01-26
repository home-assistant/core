"""Amcrest device models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

if TYPE_CHECKING:
    from . import AmcrestChecker


@dataclass
class AmcrestDevice:
    """Representation of a base Amcrest discovery device configured via YAML."""

    api: AmcrestChecker
    authentication: aiohttp.BasicAuth | None
    ffmpeg_arguments: list[str]
    stream_source: str
    resolution: int
    control_light: bool
    channel: int = 0


class AmcrestConfiguredDevice(AmcrestDevice):
    """Representation of a base Amcrest device."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        name: str,
        api: AmcrestChecker,
        authentication: aiohttp.BasicAuth | None,
        ffmpeg_arguments: list[str],
        stream_source: str,
        resolution: int,
        control_light: bool,
        channel: int = 0,
    ) -> None:
        """Initialize Amcrest device."""
        super().__init__(
            api,
            authentication,
            ffmpeg_arguments,
            stream_source,
            resolution,
            control_light,
            channel,
        )
        self.hass = hass
        self.config_entry = config_entry
        self.name = name
        self.serial_number = ""
        self.manufacturer = "Amcrest"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for device registration."""
        # Use serial number if available, otherwise fall back to config entry ID
        identifier = (
            self.serial_number if self.serial_number else self.config_entry.entry_id
        )

        # Build configuration URL from host and port
        host = self.config_entry.data["host"]
        port = self.config_entry.data.get("port", 80)
        configuration_url = f"http://{host}:{port}" if port != 80 else f"http://{host}"

        return DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=self.name,
            manufacturer="Amcrest",
            configuration_url=configuration_url,
        )

    async def async_get_data(self) -> None:
        """Get data from the device."""
        self.serial_number = await self.api.async_serial_number
