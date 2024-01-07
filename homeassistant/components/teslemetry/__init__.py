"""Teslemetry integration."""
import logging

from tesla_fleet_api import Teslemetry
from tesla_fleet_api.exceptions import AuthenticationError, TeslaFleetError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .models import TeslemetryData

PLATFORMS = [
    Platform.CLIMATE,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Teslemetry config."""

    teslemetry = Teslemetry(
        session=async_get_clientsession(hass),
        access_token=entry.data[CONF_ACCESS_TOKEN],
    )
    try:
        vehicles = await teslemetry.vehicle.create()
    except AuthenticationError as e:
        raise ConfigEntryAuthFailed from e
    except TeslaFleetError as e:
        _LOGGER.error("Setup failed, unable to connect to Teslemetry: %s", e)
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = TeslemetryData(vehicles=vehicles)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Teslemetry Config."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
