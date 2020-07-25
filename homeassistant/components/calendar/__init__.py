"""Support for Google Calendar event device sensors."""
from datetime import timedelta
import logging
import re

from aiohttp import web

from homeassistant.components import http
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import HTTP_BAD_REQUEST, STATE_OFF, STATE_ON
from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    time_period_str,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.util import dt

from .const import DOMAIN
from .legacy import CalendarListView, CalendarEventView

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up the calendar component."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await setup_legacy(hass, config)
    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(config_entry)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(config_entry)


async def setup_legacy(hass: HomeAssistant, config: Config) -> bool:
    """Track states and offer events for calendars."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    hass.http.register_view(CalendarListView(component))
    hass.http.register_view(CalendarEventView(component))

    hass.components.frontend.async_register_built_in_panel(
        "calendar", "calendar", "hass:calendar"
    )
