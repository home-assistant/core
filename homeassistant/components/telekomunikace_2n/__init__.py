"""The 2N Telekomunikace integration."""
from __future__ import annotations

from py2n import Py2NConnectionData, Py2NDevice
from py2n.exceptions import ApiError, DeviceApiError, Py2NError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .coordinator import Py2NDeviceCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up 2N Telekomunikace device from a config entry."""
    try:
        device = await Py2NDevice.create(
            aiohttp_client.async_get_clientsession(hass),
            options=Py2NConnectionData(
                host=entry.data[CONF_HOST],
                username=entry.data[CONF_USERNAME],
                password=entry.data[CONF_PASSWORD],
            ),
        )
    except DeviceApiError as err:
        if (
            err.error is ApiError.AUTHORIZATION_REQUIRED
            or ApiError.INSUFFICIENT_PRIVILEGES
        ):
            entry.async_start_reauth(hass)
    except Py2NError as err:
        raise ConfigEntryNotReady from err

    coordinator = Py2NDeviceCoordinator(hass, device)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
