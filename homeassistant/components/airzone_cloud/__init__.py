"""The Airzone Cloud integration."""

from __future__ import annotations

import logging

from aioairzone_cloud.cloudapi import AirzoneCloudApi
from aioairzone_cloud.common import ConnectionOptions

from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import CONF_DEVICE_CONFIG, DEFAULT_DEVICE_CONFIG
from .coordinator import AirzoneCloudConfigEntry, AirzoneUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: AirzoneCloudConfigEntry
) -> bool:
    """Set up Airzone Cloud from a config entry."""
    options = ConnectionOptions(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_DEVICE_CONFIG],
        True,
    )

    airzone = AirzoneCloudApi(aiohttp_client.async_get_clientsession(hass), options)
    await airzone.login()
    inst_list = await airzone.list_installations()
    for inst in inst_list:
        if inst.get_id() == entry.data[CONF_ID]:
            airzone.select_installation(inst)
            await airzone.update_installation(inst)

    coordinator = AirzoneUpdateCoordinator(hass, entry, airzone)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AirzoneCloudConfigEntry
) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        await coordinator.airzone.logout()

    return unload_ok


async def async_migrate_entry(
    hass: HomeAssistant, entry: AirzoneCloudConfigEntry
) -> bool:
    """Migrate an old entry."""
    if entry.version == 1 and entry.minor_version < 2:
        # Add missing CONF_DEVICE_CONFIG
        device_config = entry.data.get(CONF_DEVICE_CONFIG, DEFAULT_DEVICE_CONFIG)
        new_data = entry.data.copy()
        new_data[CONF_DEVICE_CONFIG] = device_config
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            minor_version=2,
        )

    _LOGGER.info(
        "Migration to configuration version %s.%s successful",
        entry.version,
        entry.minor_version,
    )

    return True
