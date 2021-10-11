"""The Efergy integration."""
from __future__ import annotations

from pyefergy import Efergy, exceptions

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_API_KEY,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import ATTRIBUTION, DATA_KEY_API, DEFAULT_NAME, DOMAIN

PLATFORMS = [SENSOR_DOMAIN]


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

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_KEY_API: api}
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class EfergyEntity(Entity):
    """Representation of a Efergy entity."""

    def __init__(
        self,
        api: Efergy,
        server_unique_id: str,
    ) -> None:
        """Initialize an Efergy entity."""
        self.api = api
        self._server_unique_id = server_unique_id
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity."""
        return {
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.api.info["mac"])},
            ATTR_IDENTIFIERS: {(DOMAIN, self._server_unique_id)},
            ATTR_MANUFACTURER: DEFAULT_NAME,
            ATTR_NAME: DEFAULT_NAME,
            ATTR_MODEL: self.api.info["type"],
            ATTR_SW_VERSION: self.api.info["version"],
        }
