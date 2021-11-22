"""The ViCare integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareDevice import Device
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_CIRCUIT,
    CONF_HEATING_TYPE,
    DEFAULT_HEATING_TYPE,
    DOMAIN,
    HEATING_TYPE_TO_CREATOR_METHOD,
    PLATFORMS,
    VICARE_API,
    VICARE_CIRCUITS,
    VICARE_DEVICE_CONFIG,
    HeatingType,
)

_LOGGER = logging.getLogger(__name__)


@dataclass()
class ViCareRequiredKeysMixin:
    """Mixin for required keys."""

    value_getter: Callable[[Device], bool]


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_CIRCUIT),
            vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Required(CONF_CLIENT_ID): cv.string,
                    vol.Optional(CONF_SCAN_INTERVAL, default=60): vol.All(
                        cv.time_period, lambda value: value.total_seconds()
                    ),
                    vol.Optional(
                        CONF_CIRCUIT
                    ): int,  # Ignored: All circuits are now supported. Will be removed when switching to Setup via UI.
                    vol.Optional(CONF_NAME, default="ViCare"): cv.string,
                    vol.Optional(
                        CONF_HEATING_TYPE, default=DEFAULT_HEATING_TYPE.value
                    ): vol.In([e.value for e in HeatingType]),
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config) -> bool:
    """Set up the ViCare component from yaml."""
    if DOMAIN not in config:
        # Setup via UI. No need to continue yaml-based setup
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DOMAIN],
        )
    )

    return True


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
    vicare_api.setCacheDuration(entry_data[CONF_SCAN_INTERVAL])
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
    hass.data[DOMAIN][entry.entry_id][VICARE_CIRCUITS] = hass.data[DOMAIN][
        entry.entry_id
    ][VICARE_API].circuits


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload ViCare config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
