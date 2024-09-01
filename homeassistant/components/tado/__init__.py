"""Support for the (unofficial) Tado API."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

import requests.exceptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_FALLBACK,
    CONST_OVERLAY_MANUAL,
    CONST_OVERLAY_TADO_DEFAULT,
    CONST_OVERLAY_TADO_MODE,
    CONST_OVERLAY_TADO_OPTIONS,
    DOMAIN,
    UPDATE_LISTENER,
    UPDATE_MOBILE_DEVICE_TRACK,
    UPDATE_TRACK,
)
from .services import setup_services
from .tado_connector import TadoConnector

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.WATER_HEATER,
]

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=4)
SCAN_INTERVAL = timedelta(minutes=5)
SCAN_MOBILE_DEVICE_INTERVAL = timedelta(seconds=30)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Tado."""

    setup_services(hass)

    return True


type TadoConfigEntry = ConfigEntry[TadoRuntimeData]


@dataclass
class TadoRuntimeData:
    """Dataclass for Tado runtime data."""

    tadoconnector: TadoConnector
    update_track: Any
    update_mobile_device_track: Any
    update_listener: Any


async def async_setup_entry(hass: HomeAssistant, entry: TadoConfigEntry) -> bool:
    """Set up Tado from a config entry."""

    _async_import_options_from_data_if_missing(hass, entry)

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    fallback = entry.options.get(CONF_FALLBACK, CONST_OVERLAY_TADO_DEFAULT)

    tadoconnector = TadoConnector(hass, username, password, fallback)

    try:
        await hass.async_add_executor_job(tadoconnector.setup)
    except KeyError:
        _LOGGER.error("Failed to login to tado")
        return False
    except RuntimeError as exc:
        _LOGGER.error("Failed to setup tado: %s", exc)
        return False
    except requests.exceptions.Timeout as ex:
        raise ConfigEntryNotReady from ex
    except requests.exceptions.HTTPError as ex:
        if ex.response.status_code > 400 and ex.response.status_code < 500:
            _LOGGER.error("Failed to login to tado: %s", ex)
            return False
        raise ConfigEntryNotReady from ex

    # Do first update
    await hass.async_add_executor_job(tadoconnector.update)

    # Poll for updates in the background
    update_track = async_track_time_interval(
        hass,
        lambda now: tadoconnector.update(),
        SCAN_INTERVAL,
    )

    update_mobile_devices = async_track_time_interval(
        hass,
        lambda now: tadoconnector.update_mobile_devices(),
        SCAN_MOBILE_DEVICE_INTERVAL,
    )

    update_listener = entry.add_update_listener(_async_update_listener)

    entry.runtime_data = TadoRuntimeData(
        tadoconnector=tadoconnector,
        update_track=update_track,
        update_mobile_device_track=update_mobile_devices,
        update_listener=update_listener,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


@callback
def _async_import_options_from_data_if_missing(hass: HomeAssistant, entry: ConfigEntry):
    options = dict(entry.options)
    if CONF_FALLBACK not in options:
        options[CONF_FALLBACK] = entry.data.get(
            CONF_FALLBACK, CONST_OVERLAY_TADO_DEFAULT
        )
        hass.config_entries.async_update_entry(entry, options=options)

    if options[CONF_FALLBACK] not in CONST_OVERLAY_TADO_OPTIONS:
        if options[CONF_FALLBACK]:
            options[CONF_FALLBACK] = CONST_OVERLAY_TADO_MODE
        else:
            options[CONF_FALLBACK] = CONST_OVERLAY_MANUAL
        hass.config_entries.async_update_entry(entry, options=options)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass.data[DOMAIN][entry.entry_id][UPDATE_TRACK]()
    hass.data[DOMAIN][entry.entry_id][UPDATE_LISTENER]()
    hass.data[DOMAIN][entry.entry_id][UPDATE_MOBILE_DEVICE_TRACK]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
