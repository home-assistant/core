"""Data update coordinator for the Control4 integration."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from pyControl4.error_handling import C4Exception

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .director_utils import update_variables_for_config_entry

if TYPE_CHECKING:
    from . import Control4ConfigEntry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


class Control4DataUpdateCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Poll a set of variables for all items from the Control4 director."""

    config_entry: Control4ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: Control4ConfigEntry,
        name: str,
        variable_names: set[str],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=SCAN_INTERVAL,
        )
        self._variable_names = variable_names

    @override
    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        """Fetch data from the Control4 director."""
        try:
            return await update_variables_for_config_entry(
                self.hass, self.config_entry, self._variable_names
            )
        except C4Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
