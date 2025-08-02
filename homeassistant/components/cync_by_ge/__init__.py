"""The Cync by GE integration."""

from __future__ import annotations

from pycync import Auth, Cync, User
from pycync.exceptions import AuthFailedError, CyncError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_AUTHORIZE_STRING,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
)
from .coordinator import CyncConfigEntry, CyncCoordinator, CyncData

_PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: CyncConfigEntry) -> bool:
    """Set up Cync by GE from a config entry."""
    user_info = User(
        entry.data[CONF_ACCESS_TOKEN],
        entry.data[CONF_REFRESH_TOKEN],
        entry.data[CONF_AUTHORIZE_STRING],
        entry.data[CONF_USER_ID],
        expires_at=entry.data[CONF_EXPIRES_AT],
    )
    cync_auth = Auth(async_get_clientsession(hass), user=user_info)

    try:
        cync = await Cync.create(cync_auth)
    except AuthFailedError as ex:
        raise ConfigEntryAuthFailed("User Token Invalid") from ex
    except CyncError as ex:
        raise ConfigEntryNotReady("Unable to connect to Cync") from ex

    logged_in_user = cync.get_logged_in_user()
    if logged_in_user.access_token != entry.data[CONF_ACCESS_TOKEN]:
        # Check for refreshed credentials and update config accordingly.
        new_data = {**entry.data}
        new_data[CONF_ACCESS_TOKEN] = logged_in_user.access_token
        new_data[CONF_REFRESH_TOKEN] = logged_in_user.refresh_token
        new_data[CONF_EXPIRES_AT] = logged_in_user.expires_at
        hass.config_entries.async_update_entry(entry, data=new_data)

    devices_coordinator = CyncCoordinator(hass, entry, cync)

    cync.set_update_callback(devices_coordinator.on_data_update)

    entry.runtime_data = CyncData(cync, devices_coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CyncConfigEntry) -> bool:
    """Unload a config entry."""
    cync = entry.runtime_data.api
    cync.shut_down()
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
