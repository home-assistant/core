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
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    DEFAULT_CACHE_DURATION,
    DEVICE_LIST,
    DOMAIN,
    PLATFORMS,
    UNSUPPORTED_DEVICES,
)
from .types import ViCareDevice
from .utils import get_device

_LOGGER = logging.getLogger(__name__)
_TOKEN_FILENAME = "vicare_token.save"


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


def vicare_login(
    hass: HomeAssistant,
    entry_data: Mapping[str, Any],
    cache_duration=DEFAULT_CACHE_DURATION,
) -> PyViCare:
    """Login via PyVicare API."""
    vicare_api = PyViCare()
    vicare_api.setCacheDuration(cache_duration)
    vicare_api.initWithCredentials(
        entry_data[CONF_USERNAME],
        entry_data[CONF_PASSWORD],
        entry_data[CONF_CLIENT_ID],
        hass.config.path(STORAGE_DIR, _TOKEN_FILENAME),
    )
    return vicare_api


def setup_vicare_api(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up PyVicare API."""
    vicare_api = vicare_login(hass, entry.data)
    device_config_list = vicare_api.devices
    for device_config in device_config_list:
        _LOGGER.debug(
            "Found device: %s (online: %s, supported: %s)",
            device_config.getModel(),
            str(device_config.isOnline()),
            str(device_config.getModel() not in UNSUPPORTED_DEVICES),
        )

    device_config_list = get_online_devices(
        hass, get_supported_devices(device_config_list)
    )
    if (number_of_devices := len(device_config_list)) > 1:
        cache_duration = DEFAULT_CACHE_DURATION * number_of_devices
        _LOGGER.debug(
            "Found %s devices, adjusting cache duration to %s",
            number_of_devices,
            cache_duration,
        )
        vicare_api = vicare_login(hass, entry.data, cache_duration)
        device_config_list = get_online_devices(
            hass, get_supported_devices(vicare_api.devices)
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
        await hass.async_add_executor_job(
            os.remove, hass.config.path(STORAGE_DIR, _TOKEN_FILENAME)
        )

    return unload_ok


def get_supported_devices(
    devices: list[PyViCareDeviceConfig],
) -> list[PyViCareDeviceConfig]:
    """Remove unsupported devices from the list."""

    _LOGGER.debug("Ignoring unsupported devices (%s)", UNSUPPORTED_DEVICES)
    return [
        device_config
        for device_config in devices
        if device_config.getModel() not in UNSUPPORTED_DEVICES
    ]


def get_online_devices(
    hass: HomeAssistant,
    devices: list[PyViCareDeviceConfig],
) -> list[PyViCareDeviceConfig]:
    """Remove offline devices from the list."""

    _LOGGER.debug("Ignoring offline devices")
    result = []
    for device_config in devices:
        if device_config.isOnline():
            result.append(device_config)
        else:
            ir.create_issue(
                hass,
                DOMAIN,
                "device_offline",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="device_offline",
                translation_placeholders={
                    "model": device_config.getModel(),
                },
            )
    return result
