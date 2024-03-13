"""Room Occupancy Binary Sensor."""
from __future__ import annotations

import logging

from homeassistant import config_entries, core
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ACTIVE_STATES,
    CONF_ENTITIES_KEEP,
    CONF_ENTITIES_TOGGLE,
    CONF_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)


async def async_setup(hass, config):
    """Set up the Room Occupancy platform."""
    _LOGGER.debug("__init__.py async_setup triggered! config: %s", config)
    return True


async def async_setup_entry(hass, entry):
    """Add entity."""
    _LOGGER.debug("__init__.py async_setup_entry triggered!")
    for field in entry.as_dict():
        _LOGGER.debug("%s: %s", field, entry.as_dict()[field])
    data = entry.as_dict()["data"]
    name = data[CONF_NAME]
    timeout = data[CONF_TIMEOUT]
    entities_toggle = data[CONF_ENTITIES_TOGGLE]
    entities_keep = data[CONF_ENTITIES_KEEP]
    active_states = data[CONF_ACTIVE_STATES]

    _LOGGER.debug(
        "name: %s, timeout %i, entities_toggle %s, entities_keep %s, active_states %s",
        name,
        timeout,
        entities_toggle,
        entities_keep,
        active_states,
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")
    )
    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry triggered!")
    data = entry.as_dict()["data"]
    _LOGGER.debug("entry_id is: %s", data)
    unload_ok = True
    if unload_ok:
        await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")
        # hass.data[DOMAIN].pop(data["entry_id"])

    return unload_ok
