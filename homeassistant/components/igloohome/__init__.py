"""The igloohome integration."""

from __future__ import annotations

from dataclasses import dataclass

from aiohttp import ClientError
from igloohome_api import (
    Api as IgloohomeApi,
    ApiException,
    Auth as IgloohomeAuth,
    AuthException,
    GetDeviceInfoResponse,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

PLATFORMS: list[Platform] = [Platform.LOCK, Platform.SENSOR]


@dataclass
class IgloohomeRuntimeData:
    """Holding class for runtime data."""

    api: IgloohomeApi
    devices: list[GetDeviceInfoResponse]


type IgloohomeConfigEntry = ConfigEntry[IgloohomeRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: IgloohomeConfigEntry) -> bool:
    """Set up igloohome from a config entry."""
    authentication = IgloohomeAuth(
        session=async_get_clientsession(hass),
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
    )

    api = IgloohomeApi(auth=authentication)
    try:
        devices = (await api.get_devices()).payload
    except AuthException as e:
        raise ConfigEntryError from e
    except (ApiException, ClientError) as e:
        raise ConfigEntryNotReady from e

    entry.runtime_data = IgloohomeRuntimeData(api, devices)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IgloohomeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
