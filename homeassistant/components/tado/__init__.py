"""Support for the (unofficial) Tado API."""

from datetime import timedelta
import logging

import PyTado
import PyTado.exceptions
from PyTado.interface import Tado

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv
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
from .services import setup_services

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

    setup_services(hass)
    return True


type TadoConfigEntry = ConfigEntry[TadoData]


async def async_setup_entry(hass: HomeAssistant, entry: TadoConfigEntry) -> bool:
    """Set up Tado from a config entry."""
    if CONF_REFRESH_TOKEN not in entry.data:
        raise ConfigEntryAuthFailed

    _async_import_options_from_data_if_missing(hass, entry)

    _LOGGER.debug("Setting up Tado connection")
    _LOGGER.debug(
        "Creating tado instance with refresh token: %s",
        entry.data[CONF_REFRESH_TOKEN],
    )

    def create_tado_instance() -> tuple[Tado, str]:
        """Create a Tado instance, this time with a previously obtained refresh token."""
        tado = Tado(saved_refresh_token=entry.data[CONF_REFRESH_TOKEN])
        return tado, tado.device_activation_status()

    try:
        tado, device_status = await hass.async_add_executor_job(create_tado_instance)
    except PyTado.exceptions.TadoWrongCredentialsException as err:
        raise ConfigEntryError(f"Invalid Tado credentials. Error: {err}") from err
    except PyTado.exceptions.TadoException as err:
        raise ConfigEntryNotReady(f"Error during Tado setup: {err}") from err
    if device_status != "COMPLETED":
        raise ConfigEntryAuthFailed(
            f"Device login flow status is {device_status}. Starting re-authentication."
        )

    _LOGGER.debug("Tado connection established")

    coordinator = TadoDataUpdateCoordinator(hass, entry, tado)
    await coordinator.async_config_entry_first_refresh()

    mobile_coordinator = TadoMobileDeviceUpdateCoordinator(hass, entry, tado)
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
