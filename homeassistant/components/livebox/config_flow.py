"""Config flow to configure Livebox."""
import asyncio
from copy import copy

import voluptuous as vol

from aiosysbus import Sysbus
from aiosysbus.exceptions import AuthorizationError

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD

from .const import (
    DOMAIN,
    LOGGER,
    DEFAULT_USERNAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    TEMPLATE_SENSOR,
    CONF_ALLOW_TRACKER,
)
from .errors import CannotConnect


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
        self.box_id = None

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
        box = Sysbus()

        try:
            await box.open(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
            )

        except AuthorizationError:
            errors["base"] = "login_inccorect"

        except CannotConnect:
            LOGGER.error("Error connecting to the Livebox at %s", self.host)
            errors["base"] = "linking"

        except Exception:  # pylint: disable=broad-except
            LOGGER.error("Unknown error connecting with Livebox at %s", self.host)
            errors["base"] = "linking"

        try:
            config = await box.system.get_deviceinfo()
            self.box_id = config["status"]["SerialNumber"]

        except Exception:
            LOGGER.error("Unique ID not found")
            return False

        await self._entry_from_box()
        return await self.async_step_options()

        # If there was no user input, do not show the errors.
        if user_input is None:
            errors = {}

        return self.async_show_form(step_id="link", errors=errors)

    async def async_step_options(self, user_input=None):
        """Step for link router."""

        options = {}
        if user_input is not None:
            options = {CONF_ALLOW_TRACKER: user_input[CONF_ALLOW_TRACKER]}
            return self.async_create_entry(
                title=f"{TEMPLATE_SENSOR}",
                data={
                    "box_id": self.box_id,
                    "host": self.host,
                    "port": self.port,
                    "username": self.username,
                    "password": self.password,
                    "options": options,
                },
            )

        return self.async_show_form(
            step_id="options",
            data_schema=vol.Schema({vol.Optional(CONF_ALLOW_TRACKER): bool}),
        )

    async def _entry_from_box(self):
        """Return a config entry from an initialized box."""

        # Remove all other entries of hubs with same ID or host
        same_hub_entries = [
            entry.entry_id
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data["box_id"] == self.box_id
        ]

        if same_hub_entries:
            await asyncio.wait(
                [
                    self.hass.config_entries.async_remove(entry_id)
                    for entry_id in same_hub_entries
                ]
            )

        return True


class LiveboxOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Livebox options."""

    def __init__(self, config_entry):
        """Initialize Livebox options flow."""
        self.config_entry = config_entry
        self.options = copy(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the Livebox options."""

        if user_input is not None:
            self.options[CONF_ALLOW_TRACKER] = user_input[CONF_ALLOW_TRACKER]
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ALLOW_TRACKER,
                        default=self.config_entry.options[CONF_ALLOW_TRACKER],
                    ): bool
                }
            ),
        )
