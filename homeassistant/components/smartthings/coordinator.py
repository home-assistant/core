"""Coordinator for SmartThings devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from pysmartthings import SmartThings
from pysmartthings.models import Attribute, Capability, Device, Scene, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


@dataclass
class SmartThingsData:
    """Define an object to hold SmartThings data."""

    devices: list[SmartThingsDeviceCoordinator]
    scenes: dict[str, Scene]
    client: SmartThings


type SmartThingsConfigEntry = ConfigEntry[SmartThingsData]


class SmartThingsDeviceCoordinator(
    DataUpdateCoordinator[dict[Capability, dict[Attribute, Status]]]
):
    """Define an object to hold device data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SmartThingsConfigEntry,
        client: SmartThings,
        device: Device,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=device.name,
            update_interval=timedelta(seconds=30),
        )
        self.client = client
        self.device = device

    async def _async_update_data(self) -> dict[Capability, dict[Attribute, Status]]:
        try:
            return (await self.client.get_device_status(self.device.device_id))["main"]
        except Exception as err:
            _LOGGER.exception("Error updating device %s", self.device.device_id)
            raise UpdateFailed("Error updating device") from err
