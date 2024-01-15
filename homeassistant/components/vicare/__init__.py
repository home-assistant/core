"""The ViCare integration."""
from __future__ import annotations

from contextlib import suppress
import logging
import os

from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import (
    PyViCareInvalidConfigurationError,
    PyViCareInvalidCredentialsError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_ACTIVE_DEVICE,
    CONF_HEATING_TYPE,
    DOMAIN,
    HEATING_TYPE_TO_CREATOR_METHOD,
    PLATFORMS,
    VICARE_API,
    VICARE_DEVICE_CONFIG,
    VICARE_DEVICE_CONFIG_LIST,
    VICARE_TOKEN_FILENAME,
    HeatingType,
)
from .utils import get_device_config_list, get_serial

_LOGGER = logging.getLogger(__name__)


def _get_active_device_for_migration(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Return the serial of the first element of the device config list (migration helper)."""
    device_list = get_device_config_list(hass, entry.data)
    # Currently we only support a single device
    return get_serial(device_list[0])


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    if entry.version == 1:
        _LOGGER.debug("Migrating from version %s", entry.version)
        serial = await hass.async_add_executor_job(
            _get_active_device_for_migration, hass, entry
        )
        entry.version = 2
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACTIVE_DEVICE: serial,
            },
        )
        _LOGGER.debug("Migration to version %s successful", entry.version)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from config entry."""
    _LOGGER.debug("Setting up ViCare component")

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {}

    try:
        await hass.async_add_executor_job(setup_vicare_api, hass, entry)
    except (PyViCareInvalidConfigurationError, PyViCareInvalidCredentialsError) as err:
        raise ConfigEntryAuthFailed("Authentication failed") from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update a given config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


def setup_vicare_api(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up PyVicare API."""
    device_list = get_device_config_list(hass, entry.data)
    # Currently we only support a single device
    device = get_configured_device(device_list, entry)
    hass.data[DOMAIN][entry.entry_id][VICARE_DEVICE_CONFIG_LIST] = device_list
    hass.data[DOMAIN][entry.entry_id][VICARE_DEVICE_CONFIG] = device
    hass.data[DOMAIN][entry.entry_id][VICARE_API] = getattr(
        device,
        HEATING_TYPE_TO_CREATOR_METHOD[HeatingType(entry.data[CONF_HEATING_TYPE])],
    )()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload ViCare config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    with suppress(FileNotFoundError):
        await hass.async_add_executor_job(
            os.remove, hass.config.path(STORAGE_DIR, VICARE_TOKEN_FILENAME)
        )

    return unload_ok


def get_configured_device(
    devices: list[PyViCareDeviceConfig],
    entry: ConfigEntry,
) -> PyViCareDeviceConfig:
    """Return the configured device."""
    active_device: str = entry.options.get(
        CONF_ACTIVE_DEVICE, entry.data.get(CONF_ACTIVE_DEVICE)
    )

    for device_config in devices:
        if get_serial(device_config) == active_device:
            return device_config
    return None
