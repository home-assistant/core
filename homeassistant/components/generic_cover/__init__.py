"""The Generic Cover integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.device import (
    async_remove_stale_devices_links_keep_entity_device,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SWITCH_CLOSE, CONF_SWITCH_OPEN, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Generic Cover component."""
    if DOMAIN not in config:
        return True

    for cover_conf in config[DOMAIN]:
        hass.async_create_task(
            discovery.async_load_platform(
                hass, Platform.COVER, DOMAIN, cover_conf, config
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    options = {**entry.data, **entry.options}

    async_remove_stale_devices_links_keep_entity_device(
        hass,
        entry.entry_id,
        options[CONF_SWITCH_OPEN],
    )
    async_remove_stale_devices_links_keep_entity_device(
        hass,
        entry.entry_id,
        options[CONF_SWITCH_CLOSE],
    )

    await hass.config_entries.async_forward_entry_setups(entry, (Platform.COVER,))
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, (Platform.COVER,))
