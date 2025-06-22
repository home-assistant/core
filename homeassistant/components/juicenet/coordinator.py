"""The JuiceNet integration."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .device import JuiceNetApi

_LOGGER = logging.getLogger(__name__)


class JuiceNetCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for JuiceNet."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, juicenet_api: JuiceNetApi
    ) -> None:
        """Initialize the JuiceNet coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="JuiceNet",
            update_interval=timedelta(seconds=30),
        )
        self.juicenet_api = juicenet_api

    async def _async_update_data(self) -> None:
        for device in self.juicenet_api.devices:
            await device.update_state(True)
