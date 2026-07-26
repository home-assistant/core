"""DataUpdateCoordinator for BleBox devices."""

from datetime import timedelta
import logging
from typing import override

from blebox_uniapi.box import Box
from blebox_uniapi.error import Error, UnauthorizedRequest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


type BleBoxConfigEntry = ConfigEntry[BleBoxCoordinator]


class BleBoxCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for a single BleBox device."""

    config_entry: BleBoxConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: BleBoxConfigEntry, box: Box
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )
        self.box = box

    @override
    async def _async_update_data(self) -> None:
        """Fetch data from the BleBox device."""
        try:
            await self.box.async_update_data()
        except UnauthorizedRequest as err:
            raise ConfigEntryAuthFailed from err
        except Error as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="data_update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
