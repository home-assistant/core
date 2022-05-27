"""The ViCare integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareDevice import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_HEATING_TYPE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HEATING_TYPE_TO_CREATOR_METHOD,
    PLATFORMS,
    VICARE_API,
    VICARE_DEVICE_CONFIG,
    HeatingType,
)

_LOGGER = logging.getLogger(__name__)


@dataclass()
class ViCareRequiredKeysMixin:
    """Mixin for required keys."""

    value_getter: Callable[[Device], bool]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from config entry."""
    _LOGGER.debug("Setting up ViCare component")

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {}

    await hass.async_add_executor_job(setup_vicare_api, hass, entry)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


def vicare_login(hass, entry_data):
    """Login via PyVicare API."""
    vicare_api = PyViCare()
    vicare_api.setCacheDuration(DEFAULT_SCAN_INTERVAL)
    vicare_api.initWithCredentials(
        entry_data[CONF_USERNAME],
        entry_data[CONF_PASSWORD],
        entry_data[CONF_CLIENT_ID],
        hass.config.path(STORAGE_DIR, "vicare_token.save"),
    )
    return vicare_api


def setup_vicare_api(hass, entry):
    """Set up PyVicare API."""
    vicare_api = vicare_login(hass, entry.data)

    for device in vicare_api.devices:
        _LOGGER.info(
            "Found device: %s (online: %s)", device.getModel(), str(device.isOnline())
        )

    # Currently we only support a single device
    device = vicare_api.devices[0]
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

    return unload_ok
