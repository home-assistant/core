"""Initialization file of the integration."""

import aiohttp
from aiopapouch import PapouchHTTPClient, create_device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .coordinator import PapouchDataUpdateCoordinator

DOMAIN = "papouch"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type PapouchConfigEntry = ConfigEntry[PapouchDataUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup (unused)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PapouchConfigEntry) -> bool:
    """Set up Papouch device from a config entry."""

    session = async_get_clientsession(hass)
    api_client = PapouchHTTPClient(entry.data["ip_address"], session)

    try:
        device = await create_device(api_client)
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to Papouch device: {err}"
        ) from err

    if device is None:
        raise ConfigEntryNotReady("Failed to identify device type")

    if entry.unique_id is None and device.mac_address:
        hass.config_entries.async_update_entry(entry, unique_id=device.mac_address)

    coordinator = PapouchDataUpdateCoordinator(hass, api_client, entry, device)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PapouchConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
