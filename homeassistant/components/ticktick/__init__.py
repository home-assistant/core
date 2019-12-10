"""The TickTick integration."""
from typing import Callable

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

from ticktick import TickTick
from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


def handle_add_task(client: TickTick) -> Callable:
    """Handle for add_task Service, returns the actual callable handler."""

    def handler(call: ServiceCall):
        title = call.data.get("title", "")
        content = call.data.get("content", "")
        project = call.data.get("project", "")
        client.add(title=title, list_name=project, extra_kwargs={"content": content})

    return handler


def setup(hass: HomeAssistant, config):
    """Set up the TickTick integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up TickTick from a config entry."""

    client = TickTick(entry.data.get(CONF_USERNAME), entry.data.get(CONF_PASSWORD))
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = client

    hass.services.async_register(DOMAIN, "add_task", handle_add_task(client))

    return True
