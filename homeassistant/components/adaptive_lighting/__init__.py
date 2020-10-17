"""Adaptive Lighting integration in Home-Assistant."""
import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_SOURCE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import (
    _DOMAIN_SCHEMA,
    ATTR_TURN_ON_OFF_LISTENER,
    CONF_NAME,
    DOMAIN,
    UNDO_UPDATE_LISTENER,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch"]


def _all_unique_names(value):
    """Validate that all entities have a unique profile name."""
    hosts = [device[CONF_NAME] for device in value]
    schema = vol.Schema(vol.Unique())
    schema(hosts)
    return value


CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [_DOMAIN_SCHEMA], _all_unique_names)},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]):
    """Import integration from config."""

    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={CONF_SOURCE: SOURCE_IMPORT}, data=entry
                )
            )
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up the component."""
    data = hass.data.setdefault(DOMAIN, {})

    undo_listener = config_entry.add_update_listener(async_update_options)
    data[config_entry.entry_id] = {UNDO_UPDATE_LISTENER: undo_listener}
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_update_options(hass, config_entry: ConfigEntry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        config_entry, "switch"
    )
    data = hass.data[DOMAIN]
    data[config_entry.entry_id][UNDO_UPDATE_LISTENER]()
    if unload_ok:
        data.pop(config_entry.entry_id)

    if len(data) == 1 and ATTR_TURN_ON_OFF_LISTENER in data:
        # no more config_entries
        turn_on_off_listener = data.pop(ATTR_TURN_ON_OFF_LISTENER)
        turn_on_off_listener.remove_listener()
        turn_on_off_listener.remove_listener2()

    if not data:
        hass.data.pop(DOMAIN)

    return unload_ok
