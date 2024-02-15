"""The ViCare integration."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
import logging
import os
from typing import Any

from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import (
    PyViCareInvalidConfigurationError,
    PyViCareInvalidCredentialsError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import STORAGE_DIR

from .const import DEFAULT_CACHE_DURATION, DEVICE_LIST, DOMAIN, PLATFORMS
from .types import ViCareDevice
from .utils import get_device, get_token_path

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.version == 1:
        _LOGGER.debug("Migrating from version %s", entry.version)

        old_token_file = hass.config.path(STORAGE_DIR, "vicare_token.save")
        if os.path.isfile(old_token_file):
            _LOGGER.debug("Removing old token file %s", old_token_file)
            await hass.async_add_executor_job(os.remove, old_token_file)

        entry.version = 2
        _LOGGER.debug("Migration to version %s successful", entry.version)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from config entry."""
    _LOGGER.debug("Setting up ViCare component %s", entry.title)

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if entry.entry_id not in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry.entry_id] = {}

    try:
        await hass.async_add_executor_job(setup_vicare_api, hass, entry)
    except (PyViCareInvalidConfigurationError, PyViCareInvalidCredentialsError) as err:
        raise ConfigEntryAuthFailed("Authentication failed") from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def vicare_login(
    entry_data: Mapping[str, Any],
    token_file: str,
    cache_duration=DEFAULT_CACHE_DURATION,
) -> PyViCare:
    """Login via PyVicare API."""
    vicare_api = PyViCare()
    vicare_api.setCacheDuration(cache_duration)
    vicare_api.initWithCredentials(
        entry_data[CONF_USERNAME],
        entry_data[CONF_PASSWORD],
        entry_data[CONF_CLIENT_ID],
        token_file,
    )
    return vicare_api


def setup_vicare_api(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up PyVicare API."""
    token_path = get_token_path(hass, entry)
    vicare_api = vicare_login(entry.data, token_path)

    device_config_list = get_supported_devices(vicare_api.devices)
    if (number_of_devices := len(device_config_list)) > 1:
        cache_duration = DEFAULT_CACHE_DURATION * number_of_devices
        _LOGGER.debug(
            "Found %s devices, adjusting cache duration to %s",
            number_of_devices,
            cache_duration,
        )
        vicare_api = vicare_login(entry.data, token_path, cache_duration)
        device_config_list = get_supported_devices(vicare_api.devices)

    for device in device_config_list:
        _LOGGER.debug(
            "Found device: %s (online: %s)", device.getModel(), str(device.isOnline())
        )

    hass.data[DOMAIN][entry.entry_id][DEVICE_LIST] = [
        ViCareDevice(config=device_config, api=get_device(entry, device_config))
        for device_config in device_config_list
    ]


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload ViCare config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    with suppress(FileNotFoundError):
        await hass.async_add_executor_job(os.remove, get_token_path(hass, entry))

    return unload_ok


def get_supported_devices(
    devices: list[PyViCareDeviceConfig],
) -> list[PyViCareDeviceConfig]:
    """Remove unsupported devices from the list."""
    return [
        device_config
        for device_config in devices
        if device_config.getModel() not in ["Heatbox1", "Heatbox2_SRC"]
    ]
