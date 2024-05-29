"""The Sensibo component."""

from __future__ import annotations

from pysensibo.exceptions import AuthenticationError

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, LOGGER, PLATFORMS
from .coordinator import SensiboDataUpdateCoordinator
from .util import NoDevicesError, NoUsernameError, async_validate_api

type SensiboConfigEntry = ConfigEntry[SensiboDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SensiboConfigEntry) -> bool:
    """Set up Sensibo from a config entry."""

    coordinator = SensiboDataUpdateCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Sensibo config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    # Change entry unique id from api_key to username
    if entry.version == 1:
        api_key = entry.data[CONF_API_KEY]

        try:
            new_unique_id = await async_validate_api(hass, api_key)
        except (AuthenticationError, ConnectionError, NoDevicesError, NoUsernameError):
            return False

        LOGGER.debug("Migrate Sensibo config entry unique id to %s", new_unique_id)
        hass.config_entries.async_update_entry(
            entry,
            unique_id=new_unique_id,
            version=2,
        )

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> bool:
    """Remove Sensibo config entry from a device."""
    entity_registry = er.async_get(hass)
    for identifier in device.identifiers:
        if identifier[0] == DOMAIN and entity_registry.async_get_entity_id(
            CLIMATE_DOMAIN, DOMAIN, identifier[1]
        ):
            return False

    return True
