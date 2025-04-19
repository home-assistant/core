"""The Kohler Energy Management (KEM) integration."""

from __future__ import annotations

import logging

from aiokem import AioKem, AuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CE_RT_COORDINATORS,
    CE_RT_HOMES,
    CE_RT_KEM,
    CONNECTION_EXCEPTIONS,
    DD_DEVICES,
    DD_DISPLAY_NAME,
    DD_ID,
    DOMAIN,
)
from .coordinator import KemUpdateCoordinator
from .kem import HAAioKem

PLATFORMS: list[str] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up KEM from a config entry."""
    websession = async_get_clientsession(hass)
    kem = HAAioKem(session=websession, hass=hass, config_entry=entry)
    try:
        await kem.login()
    except AuthenticationError as ex:
        raise ConfigEntryAuthFailed from ex
    except CONNECTION_EXCEPTIONS as ex:
        raise ConfigEntryNotReady from ex

    entry.runtime_data = {}
    entry.runtime_data[CE_RT_COORDINATORS] = {}
    entry.runtime_data[CE_RT_KEM] = kem

    homes = await kem.get_homes()
    entry.runtime_data[CE_RT_HOMES] = homes
    for home_data in homes:
        for device_data in home_data[DD_DEVICES]:
            device_id = device_data[DD_ID]
            coordinator = KemUpdateCoordinator(
                hass=hass,
                logger=_LOGGER,
                config_entry=entry,
                home_data=home_data,
                device_id=device_id,
                device_data=device_data,
                kem=kem,
                name=f"{DOMAIN} {device_data[DD_DISPLAY_NAME]}",
            )
            await coordinator.async_config_entry_first_refresh()
            entry.runtime_data[CE_RT_COORDINATORS][device_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    kem: AioKem = entry.runtime_data.get(CE_RT_KEM)
    if kem:
        await kem.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
