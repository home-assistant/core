"""Amcrest device models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

if TYPE_CHECKING:
    from . import AmcrestChecker


class AmcrestConfiguredDevice:
    """Representation of an Amcrest device configured via config flow."""

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
        """Initialize Amcrest configured device."""
        self.hass = hass
        self.config_entry = config_entry
        self.name = name
        self.api = api
        self.authentication = authentication
        self.ffmpeg_arguments = ffmpeg_arguments
        self.stream_source = stream_source
        self.resolution = resolution
        self.control_light = control_light
        self.channel = channel
        self.serial_number = ""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for device registration."""
        identifier = self.serial_number or self.config_entry.entry_id
        host = self.config_entry.data["host"]
        port = self.config_entry.data.get("port", 80)
        configuration_url = f"http://{host}:{port}" if port != 80 else f"http://{host}"

        return DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=self.name,
            manufacturer="Amcrest",
            configuration_url=configuration_url,
        )
