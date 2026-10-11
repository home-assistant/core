"""Initialization file of the integration."""

from typing import TYPE_CHECKING

import aiohttp
from aiopapouch import PapouchHTTPClient, create_network_device
from aiopapouch.exceptions import DeviceAuthError, DeviceConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_WEB_PORT, DOMAIN, UNKNOWN_LOCATION, UNKNOWN_NAME
from .coordinator import PapouchNetworkDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR]

type PapouchConfigEntry = ConfigEntry[PapouchNetworkDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PapouchConfigEntry) -> bool:
    """Set up Papouch device from a config entry."""

    session = async_get_clientsession(hass)
    password = entry.data.get(CONF_PASSWORD, "")
    web_port = entry.data.get(CONF_PORT, DEFAULT_WEB_PORT)
    api_client = PapouchHTTPClient(
        entry.data[CONF_IP_ADDRESS], session, password=password or "", web_port=web_port
    )

    try:
        name, location = await api_client.get_device_info()
    except (DeviceConnectionError, DeviceAuthError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err

    safe_name = name or UNKNOWN_NAME
    safe_location = location or UNKNOWN_LOCATION

    try:
        device = await create_network_device(api_client)
    except aiohttp.ClientResponseError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders={"name": safe_name, "location": safe_location},
        ) from err

    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect_device",
            translation_placeholders={"name": safe_name, "location": safe_location},
        ) from err

    if device is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="unsupported_device",
            translation_placeholders={"name": safe_name, "location": safe_location},
        )

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        # MAC address is stored in identifier field
        connections={(dr.CONNECTION_NETWORK_MAC, device.conf.identifier)},
        identifiers={(DOMAIN, device.conf.identifier)},
        name=device.conf.name,
        manufacturer=device.conf.manufacturer,
        model=device.conf.name,
        suggested_area=device.conf.location,
    )

    coordinator = PapouchNetworkDataUpdateCoordinator(hass, api_client, entry, device)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PapouchConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
