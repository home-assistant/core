# -*- coding: utf-8 -*-
"""
Support for AIS Google Home

For more details about this component, please refer to the documentation at
https://ai-speaker.com
"""
import asyncio
import logging
from homeassistant.components import ais_cloud
from .const import DOMAIN
from .config_flow import configured_google_homes

aisCloud = ais_cloud.AisCloudWS()

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Register the service."""

    def ask_google_home(call):
        # TODO
        pass

    hass.services.async_register(DOMAIN, "ask_google_home", ask_google_home)

    return True


async def async_setup_entry(hass, config_entry):
    """Set up config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    # TODO remove from cloud

    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    return True
