"""The brunt component."""

from __future__ import annotations

from asyncio import timeout
import logging

from aiohttp.client_exceptions import ClientResponseError, ServerDisconnectedError
from brunt import BruntClientAsync, Thing

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import REGULAR_INTERVAL

_LOGGER = logging.getLogger(__name__)

type BruntConfigEntry = ConfigEntry[BruntCoordinator]


class BruntCoordinator(DataUpdateCoordinator[dict[str | None, Thing]]):
    """Config entry data."""

    bapi: BruntClientAsync
    config_entry: BruntConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BruntConfigEntry,
    ) -> None:
        """Initialize the Brunt coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="brunt",
            update_interval=REGULAR_INTERVAL,
        )

    async def _async_setup(self) -> None:
        session = async_get_clientsession(self.hass)

        self.bapi = BruntClientAsync(
            username=self.config_entry.data[CONF_USERNAME],
            password=self.config_entry.data[CONF_PASSWORD],
            session=session,
        )
        try:
            await self.bapi.async_login()
        except ServerDisconnectedError as exc:
            raise ConfigEntryNotReady("Brunt not ready to connect.") from exc
        except ClientResponseError as exc:
            raise ConfigEntryAuthFailed(
                f"Brunt could not connect with username: {self.config_entry.data[CONF_USERNAME]}."
            ) from exc

    async def _async_update_data(self) -> dict[str | None, Thing]:
        """Fetch data from the Brunt endpoint for all Things.

        Error 403 is the API response for any kind of authentication error (failed password or email)
        Error 401 is the API response for things that are not part of the account, could happen when a device is deleted from the account.
        """
        try:
            async with timeout(10):
                things = await self.bapi.async_get_things(force=True)
                return {thing.serial: thing for thing in things}
        except ServerDisconnectedError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except ClientResponseError as err:
            if err.status == 403:
                raise ConfigEntryAuthFailed from err
            if err.status == 401:
                _LOGGER.warning("Device not found, will reload Brunt integration")
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            raise UpdateFailed from err
