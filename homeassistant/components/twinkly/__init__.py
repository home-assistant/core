"""The twinkly component."""

from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError
from ttls.client import Twinkly

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ATTR_VERSION, DOMAIN

PLATFORMS = [Platform.LIGHT]


@dataclass
class TwinklyData:
    """Data for Twinkly integration."""

    client: Twinkly
    device_info: dict[str, Any]
    sw_version: str


type TwinklyConfigEntry = ConfigEntry[TwinklyData]


async def async_setup_entry(hass: HomeAssistant, entry: TwinklyConfigEntry) -> bool:
    """Set up entries from config flow."""
    hass.data.setdefault(DOMAIN, {})

    # We setup the client here so if at some point we add any other entity for this device,
    # we will be able to properly share the connection.
    host = entry.data[CONF_HOST]

    client = Twinkly(host, async_get_clientsession(hass))

    try:
        device_info = await client.get_details()
        software_version = await client.get_firmware_version()
    except (TimeoutError, ClientError) as exception:
        raise ConfigEntryNotReady from exception

    entry.runtime_data = TwinklyData(
        client, device_info, software_version.get(ATTR_VERSION)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TwinklyConfigEntry) -> bool:
    """Remove a twinkly entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
