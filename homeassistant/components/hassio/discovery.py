"""Implement the serivces discovery feature from Hass.io for Add-ons."""
import asyncio
import logging
import os

import voluptuous as vol

from homeassistant.core import callback

from . import DOMAIN as HASSIO_DOMAIN
from .handler import HassIO, HassioAPIError

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_discovery(hass, hassio):
    """Discovery setup."""

    @callback
    def async_discovery_event_handler(event):
        """Handle events from Hass.io discovery."""


async def async_process_discovery(hass, data):
    """Process a discovery request."""
