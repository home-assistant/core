"""The Efergy integration."""

from __future__ import annotations

from pyefergy import Efergy, exceptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DEFAULT_NAME, DOMAIN

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Efergy from a config entry."""
    api = Efergy(
        entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
        utc_offset=hass.config.time_zone,
        currency=hass.config.currency,
    )

    try:
        await api.async_status(get_sids=True)
    except (exceptions.ConnectError, exceptions.DataError) as ex:
        raise ConfigEntryNotReady(f"Failed to connect to device: {ex}") from ex
    except exceptions.InvalidAuth as ex:
        raise ConfigEntryAuthFailed(
            "API Key is no longer valid. Please reauthenticate"
        ) from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class EfergyEntity(Entity):
    """Representation of a Efergy entity."""

    _attr_attribution = "Data provided by Efergy"

    def __init__(self, api: Efergy, server_unique_id: str) -> None:
        """Initialize an Efergy entity."""
        self.api = api
        self._attr_device_info = DeviceInfo(
            configuration_url="https://engage.efergy.com/user/login",
            connections={(dr.CONNECTION_NETWORK_MAC, api.info["mac"])},
            identifiers={(DOMAIN, server_unique_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
            model=api.info["type"],
            sw_version=api.info["version"],
        )
