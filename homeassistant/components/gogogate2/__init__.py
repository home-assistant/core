"""The gogogate2 component."""
import asyncio

from homeassistant.components.cover import DOMAIN as COVER
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from .common import get_data_update_coordinator
from .const import DEVICE_TYPE_GOGOGATE2

PLATFORMS = [COVER, SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Do setup of Gogogate2."""

    # Update the config entry.
    config_updates = {}
    if CONF_DEVICE not in config_entry.data:
        config_updates["data"] = {
            **config_entry.data,
            **{CONF_DEVICE: DEVICE_TYPE_GOGOGATE2},
        }

    if config_updates:
        hass.config_entries.async_update_entry(config_entry, **config_updates)

    data_update_coordinator = get_data_update_coordinator(hass, config_entry)
    await data_update_coordinator.async_config_entry_first_refresh()

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Gogogate2 config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    return unload_ok
