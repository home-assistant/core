"""Initialization file of the integration."""

import aiohttp
from aiopapouch import PapouchHTTPClient, create_device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
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
    password = entry.data.get("password", "")
    api_client = PapouchHTTPClient(entry.data["ip_address"], session, password=password)

    try:
        device = await create_device(api_client)
    except aiohttp.ClientResponseError as err:
        if err.status == 401:
            raise ConfigEntryAuthFailed(
                f"Invalid authentication for Papouch device at {api_client.ip_address}, error: {err}"
            ) from err

        raise ConfigEntryNotReady(
            f"Failed to connect to Papouch device at {api_client.ip_address}, error: {err}"
        ) from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to Papouch device at {api_client.ip_address}, error: {err}"
        ) from err

    if device is None:
        raise ConfigEntryNotReady("Failed to identify device type")

    if entry.unique_id is None and device.mac_address:
        hass.config_entries.async_update_entry(entry, unique_id=device.mac_address)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, device.mac_address)},
        identifiers={(DOMAIN, device.mac_address)},
        name=device.name,
        manufacturer=device.manufacturer,
        model=device.name,
        suggested_area=device.location,
    )

    coordinator = PapouchDataUpdateCoordinator(hass, api_client, entry, device)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PapouchConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
