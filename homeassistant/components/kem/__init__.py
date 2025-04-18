"""The Oncue integration."""

from __future__ import annotations

import logging

from aiokem import AioKem, AuthenticationCredentialsError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONNECTION_EXCEPTIONS
from .coordinator import KemUpdateCoordinator

PLATFORMS: list[str] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Oncue from a config entry."""
    data = entry.data
    websession = async_get_clientsession(hass)
    kem = AioKem(session=websession)
    try:
        await kem.authenticate(data[CONF_USERNAME], data[CONF_PASSWORD])
    except AuthenticationCredentialsError as ex:
        raise ConfigEntryAuthFailed from ex
    except CONNECTION_EXCEPTIONS as ex:
        raise ConfigEntryNotReady from ex

    entry.runtime_data = {}
    entry.runtime_data["coordinators"] = {}
    entry.runtime_data["kem"] = kem

    homes = await kem.get_homes()
    entry.runtime_data["homes"] = homes
    for home_data in homes:
        for device_data in home_data["devices"]:
            device_id = device_data["id"]
            coordinator = KemUpdateCoordinator(
                hass=hass,
                logger=_LOGGER,
                config_entry=entry,
                home_data=home_data,
                device_id=device_id,
                device_data=device_data,
                kem=kem,
                name=f"kem {device_data['displayName']}",
            )
            await coordinator.async_config_entry_first_refresh()
            entry.runtime_data["coordinators"][device_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
