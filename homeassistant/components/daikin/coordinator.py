"""Coordinator for Daikin integration."""

from datetime import timedelta
import logging

from pydaikin.daikin_base import Appliance

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DaikinCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Daikin data."""

    def __init__(self, hass: HomeAssistant, device: Appliance) -> None:
        """Initialize global Daikin data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=device.values.get("name", DOMAIN),
            update_interval=timedelta(seconds=60),
        )
        self.device = device

    async def _async_update_data(self) -> None:
        await self.device.update_status()
