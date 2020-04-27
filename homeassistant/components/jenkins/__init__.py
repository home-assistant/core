"""Initialise common parts for the Jenkins integration."""

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the AdGuard Home components."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Jenkins from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True
