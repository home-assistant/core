"""DataUpdateCoordinator for the Rotarex integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

import aiohttp
from rotarex_dimes_srg_api import InvalidAuth, RotarexApi, RotarexTank

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import RotarexConfigEntry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


class RotarexDataUpdateCoordinator(DataUpdateCoordinator[dict[str, RotarexTank]]):
    """Class to manage fetching Rotarex data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RotarexConfigEntry,
    ) -> None:
        """Initialize the data update coordinator."""
        session = async_get_clientsession(hass)
        self.api = RotarexApi(session)
        self.api.set_credentials(
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

    async def _async_setup(self) -> None:
        """Set up the coordinator with initial authentication check."""
        assert self.config_entry is not None
        try:
            await self.api.login(
                self.config_entry.data[CONF_EMAIL],
                self.config_entry.data[CONF_PASSWORD],
            )
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

    async def _async_update_data(self) -> dict[str, RotarexTank]:
        """Fetch data from API endpoint."""
        try:
            tanks = await self.api.fetch_tanks()
            return {tank.guid: tank for tank in tanks}
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching Rotarex data")
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
