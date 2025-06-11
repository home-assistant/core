"""Coordinator for the ONVIF integration."""

from datetime import timedelta
import logging

from zeep.helpers import serialize_object

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .device import ONVIFDevice

_LOGGER = logging.getLogger(__name__)

type OnvifConfigEntry = ConfigEntry[OnvifDataUpdateCoordinator]


class OnvifDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Data update coordinator for the Onvif integration."""

    config_entry: OnvifConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: OnvifConfigEntry, device: ONVIFDevice
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.device = device

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint."""
        profile = self.device.profiles[0]
        settings = await self.device.async_get_imaging_settings(profile)
        return serialize_object(settings)
