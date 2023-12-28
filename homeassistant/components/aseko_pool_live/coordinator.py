"""The Aseko Pool Live integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aioaseko import Unit, Variable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class AsekoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Variable]]):
    """Class to manage fetching Aseko unit data from single endpoint."""

    def __init__(self, hass: HomeAssistant, unit: Unit) -> None:
        """Initialize global Aseko unit data updater."""
        self._unit = unit

        if self._unit.name:
            name = self._unit.name
        else:
            name = f"{self._unit.type}-{self._unit.serial_number}"

        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(minutes=2),
        )

    async def _async_update_data(self) -> dict[str, Variable]:
        """Fetch unit data."""
        await self._unit.get_state()
        return {variable.type: variable for variable in self._unit.variables}
