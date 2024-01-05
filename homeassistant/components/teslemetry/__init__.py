"""Teslemetry integration."""
from http import HTTPStatus
import logging

from aiohttp import ClientError
from tesla_fleet_api import TeslaFleetError, Teslemetry

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN
from .models import TeslemetryVehicle

PLATFORMS = [
    Platform.CLIMATE,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Teslemetry config."""
    access_token = entry.data[CONF_ACCESS_TOKEN]

    api = Teslemetry(access_token)
    try:
        api.vehicles.list()
    except TeslaFleetError as e:
        if e.status == HTTPStatus.UNAUTHORIZED:
            raise ConfigEntryAuthFailed from e
        _LOGGER.error("Setup failed, unable to connect to Teslemetry: %s", e)
        return False
    except ClientError as e:
        raise ConfigEntryNotReady from e

    data = [
        TeslemetryVehicle(
            state_coordinator=TeslemetryStateUpdateCoordinator(
                hass,
                api_key=api_key,
                vin=vehicle["vin"],
                data=vehicle["last_state"],
            )
        )
        for vehicle in vehicles["results"]
        if vehicle["last_state"] is not None
    ]

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Teslemetry Config."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
