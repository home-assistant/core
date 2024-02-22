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

from .const import DATA_BAPI, DATA_COOR, DOMAIN, PLATFORMS, REGULAR_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Brunt using config flow."""
    session = async_get_clientsession(hass)
    bapi = BruntClientAsync(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )
    try:
        await bapi.async_login()
    except ServerDisconnectedError as exc:
        raise ConfigEntryNotReady("Brunt not ready to connect.") from exc
    except ClientResponseError as exc:
        raise ConfigEntryAuthFailed(
            f"Brunt could not connect with username: {entry.data[CONF_USERNAME]}."
        ) from exc

    async def async_update_data() -> dict[str | None, Thing]:
        """Fetch data from the Brunt endpoint for all Things.

        Error 403 is the API response for any kind of authentication error (failed password or email)
        Error 401 is the API response for things that are not part of the account, could happen when a device is deleted from the account.
        """
        try:
            async with timeout(10):
                things = await bapi.async_get_things(force=True)
                return {thing.serial: thing for thing in things}
        except ServerDisconnectedError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except ClientResponseError as err:
            if err.status == 403:
                raise ConfigEntryAuthFailed() from err
            if err.status == 401:
                _LOGGER.warning("Device not found, will reload Brunt integration")
                await hass.config_entries.async_reload(entry.entry_id)
            raise UpdateFailed from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="brunt",
        update_method=async_update_data,
        update_interval=REGULAR_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_BAPI: bapi, DATA_COOR: coordinator}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
