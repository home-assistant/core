"""DataUpdateCoordinator for the Rotarex integration."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from rotarex_dimes_srg_api import (
    InvalidAuth,
    RotarexApi,
    RotarexConnectionError,
    RotarexError,
    RotarexTank,
)

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import RotarexConfigEntry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


class RotarexDataUpdateCoordinator(DataUpdateCoordinator[dict[str, RotarexTank]]):
    """Class to manage fetching Rotarex data."""

    config_entry: RotarexConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RotarexConfigEntry,
    ) -> None:
        """Initialize the data update coordinator."""
        self.api = RotarexApi(
            async_get_clientsession(hass),
            config_entry.data[CONF_EMAIL],
            config_entry.data[CONF_PASSWORD],
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator with initial authentication check."""
        try:
            await self.api.login()
        except InvalidAuth as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except RotarexConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

    @override
    async def _async_update_data(self) -> dict[str, RotarexTank]:
        """Fetch data from API endpoint."""
        try:
            tanks = await self.api.fetch_tanks()
        except RotarexError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
        return {tank.guid: tank for tank in tanks}
