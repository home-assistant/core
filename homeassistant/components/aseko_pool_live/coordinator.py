"""The Aseko Pool Live integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from aioaseko import Aseko, Unit

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AsekoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Unit]]):
    """Class to manage fetching Aseko unit data from single endpoint."""

    def __init__(self, hass: HomeAssistant, aseko: Aseko) -> None:
        """Initialize global Aseko unit data updater."""
        self._aseko = aseko

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=2),
        )

    async def _async_update_data(self) -> dict[str, Unit]:
        """Fetch unit data."""
        units = await self._aseko.get_units()
        return {unit.serial_number: unit for unit in units}
