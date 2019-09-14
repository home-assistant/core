"""Config flow to configure Livebox."""
import logging
import asyncio
from collections import namedtuple

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD

from . import LiveboxData
from .const import (
    DOMAIN,
    LOGGER,
    DEFAULT_USERNAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    TEMPLATE_SENSOR,
)

_LOGGER = logging.getLogger(__name__)


class LiveboxFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Livebox config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the Livebox flow."""

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): str,
                vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        if user_input is not None:
            return await self.async_step_link(user_input)

        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_link(self, user_input=None):
        """Step for link router."""

        errors = {}
        try:
            user_entry = namedtuple("user_entry", "data")
            entry = user_entry(user_input)
            ld = LiveboxData(entry)
            await ld.async_conn()

        except Exception:  # pylint: disable=broad-except
            LOGGER.error("Unknown error connecting with Livebox at %s", self.host)
            errors["base"] = "linking"

        try:
            id = (await ld.async_infos())["SerialNumber"]

        except Exception:
            LOGGER.error("Unique ID not found")
            return False

        if await self._entry_from_box(id):
            return self.async_create_entry(
                title=f"{TEMPLATE_SENSOR}",
                data={
                    "id": id,
                    "host": user_input["host"],
                    "port": user_input["port"],
                    "username": user_input["username"],
                    "password": user_input["password"],
                },
            )

        return self.async_show_form(step_id="link", errors=errors)

    async def _entry_from_box(self, id):
        """Return a config entry from an initialized box."""

        # Remove all other entries of hubs with same ID or host
        same_hub_entries = [
            entry.entry_id
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data["id"] == id
        ]

        if same_hub_entries:
            await asyncio.wait(
                [
                    self.hass.config_entries.async_remove(entry_id)
                    for entry_id in same_hub_entries
                ]
            )

        return True
