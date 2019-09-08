"""Config flow to configure Livebox."""
import asyncio
from copy import copy

import voluptuous as vol

from aiosysbus import Sysbus

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD

from .const import DOMAIN, LOGGER, DEFAULT_USERNAME, DEFAULT_HOST, DEFAULT_PORT
from .errors import AuthenticationRequired, CannotConnect


class LiveboxFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Livebox config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return LiveboxOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the Livebox flow."""
        self.host = None
        self.port = None
        self.username = None
        self.password = None

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
            self.host = user_input[CONF_HOST]
            self.port = user_input[CONF_PORT]
            self.username = user_input[CONF_USERNAME]
            self.password = user_input[CONF_PASSWORD]
            return await self.async_step_link()

        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_link(self, user_input=None):
        """Step for link router."""

        errors = {}

        try:
            box = Sysbus()
            await box.open(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
            )
            return await self._entry_from_box(box)

        except AuthenticationRequired:
            errors["base"] = "register_failed"

        except CannotConnect:
            LOGGER.error("Error connecting to the Livebox at %s", self.host)
            errors["base"] = "linking"

        except Exception:  # pylint: disable=broad-except
            LOGGER.error("Unknown error connecting with Livebox at %s", self.host)
            errors["base"] = "linking"

        # If there was no user input, do not show the errors.
        if user_input is None:
            errors = {}

        return self.async_show_form(step_id="link", errors=errors)

    async def _entry_from_box(self, box):
        """Return a config entry from an initialized box."""
        config = await box.system.get_deviceinfo()
        box_id = config["status"]["SerialNumber"]

        # Remove all other entries of hubs with same ID or host
        same_hub_entries = [
            entry.entry_id
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data["box_id"] == box_id
        ]

        if same_hub_entries:
            await asyncio.wait(
                [
                    self.hass.config_entries.async_remove(entry_id)
                    for entry_id in same_hub_entries
                ]
            )

        return self.async_create_entry(
            title="Orange Livebox",
            data={
                "box_id": box_id,
                "host": self.host,
                "port": self.port,
                "username": self.username,
                "password": self.password,
            },
        )


class LiveboxOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Livebox options."""

    def __init__(self, config_entry):
        """Initialize Livebox options flow."""
        self.config_entry = config_entry
        self.options = copy(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the Livebox options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Optional("allow_tracker", default=True): bool}),
        )
