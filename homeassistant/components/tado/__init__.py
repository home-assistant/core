"""Support for the (unofficial) Tado API."""

from datetime import timedelta
import logging

from tadoasync import Tado

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_FALLBACK,
    CONF_REFRESH_TOKEN,
    CONST_OVERLAY_MANUAL,
    CONST_OVERLAY_TADO_DEFAULT,
    CONST_OVERLAY_TADO_MODE,
    CONST_OVERLAY_TADO_OPTIONS,
    DOMAIN,
)
from .coordinator import TadoDataUpdateCoordinator, TadoMobileDeviceUpdateCoordinator
from .models import TadoData
from .services import async_setup_services

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=4)
SCAN_INTERVAL = timedelta(minutes=5)
SCAN_MOBILE_DEVICE_INTERVAL = timedelta(seconds=30)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Tado."""

    async_setup_services(hass)
    return True


type TadoConfigEntry = ConfigEntry[TadoData]


async def async_setup_entry(hass: HomeAssistant, entry: TadoConfigEntry) -> bool:
    """Set up Tado from a config entry."""
    if CONF_REFRESH_TOKEN not in entry.data:
        raise ConfigEntryAuthFailed

    _async_import_options_from_data_if_missing(hass, entry)

    _LOGGER.debug("Refresh token: %s", entry.data[CONF_REFRESH_TOKEN])

    client = Tado(
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        session=async_get_clientsession(hass),
        debug=True,  # TODO: remove debug=True later
    )
    await client.async_init()

    coordinator = TadoDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    mobile_coordinator = TadoMobileDeviceUpdateCoordinator(hass, entry, client)
    await mobile_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = TadoData(coordinator, mobile_coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: TadoConfigEntry) -> bool:
    """Migrate old entry."""

    if entry.version < 2:
        _LOGGER.debug("Migrating Tado entry to version 2. Current data: %s", entry.data)
        data = dict(entry.data)
        data.pop(CONF_USERNAME, None)
        data.pop(CONF_PASSWORD, None)
        hass.config_entries.async_update_entry(entry=entry, data=data, version=2)
        _LOGGER.debug("Migration to version 2 successful")
    return True


@callback
def _async_import_options_from_data_if_missing(
    hass: HomeAssistant, entry: TadoConfigEntry
):
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


async def async_unload_entry(hass: HomeAssistant, entry: TadoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
