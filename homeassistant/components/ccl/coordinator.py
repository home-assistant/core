"""The CCL Data Update Coordinator."""

from __future__ import annotations

import logging

from aioccl import CCLDevice, CCLSensor

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class CCLCoordinator(DataUpdateCoordinator[dict[str, dict[str, CCLSensor]]]):
    """Class to manage processing CCL data."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: CCLDevice,
    ) -> None:
        """Initialize global CCL data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            always_update=True,
        )
        self.device = device

    async def _async_update_data(self) -> dict[str, dict[str, CCLSensor]]:
        """Fetch data from CCL device."""
        return self.device.get_data

    def async_push_update(self, data) -> None:
        """Process data and update coordinator."""
        self.async_set_updated_data(data)
