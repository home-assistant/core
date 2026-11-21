"""Initialization file of the integration."""

from typing import TYPE_CHECKING

from aiopapouch import PapouchHTTPClient, create_network_device
from aiopapouch.exceptions import (
    DeviceAuthError,
    DeviceConnectionError,
    DeviceParseError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_WEB_PORT, DOMAIN, UNKNOWN_LOCATION, UNKNOWN_NAME
from .coordinator import PapouchNetworkDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.SENSOR]

type PapouchConfigEntry = ConfigEntry[PapouchNetworkDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PapouchConfigEntry) -> None:
    """Set up Papouch device from a config entry."""

    session = async_get_clientsession(hass)
    password = entry.data.get(CONF_PASSWORD)
    web_port = entry.data.get(CONF_PORT, DEFAULT_WEB_PORT)

    # aiopapouch library expects an empty string instead of None for unauthenticated devices
    api_client = PapouchHTTPClient(
        entry.data[CONF_IP_ADDRESS], session, password=password or "", web_port=web_port
    )

    # note that now we will access name and location
    # of the device , first right below
    # and second in the create_network_device

    # this is done so a user will know that the device
    # he tried to create is unsupported and he will
    # see its name and location

    try:
        name, location = await api_client.get_device_info()
    except DeviceAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except DeviceConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except DeviceParseError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="parsing_error",
        ) from err

    placeholders = {
        "name": name or UNKNOWN_NAME,
        "location": location or UNKNOWN_LOCATION,
    }

    try:
        device = await create_network_device(api_client)
    except DeviceAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth_with_info",
            translation_placeholders=placeholders,
        ) from err
    except DeviceConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect_with_info",
            translation_placeholders=placeholders,
        ) from err
    except DeviceParseError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="parsing_error_with_info",
            translation_placeholders=placeholders,
        ) from err

    if device is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="unsupported_device",
            translation_placeholders=placeholders,
        )

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        # MAC address is stored in the identifier field
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


async def async_unload_entry(hass: HomeAssistant, entry: PapouchConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
