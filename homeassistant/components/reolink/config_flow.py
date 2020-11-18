"""Config flow for the Reolink camera component."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .base import ReolinkBase
from .const import (
    BASE,
    CONF_CHANNEL,
    CONF_MOTION_OFF_DELAY,
    CONF_PROTOCOL,
    CONF_STREAM,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ReolinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Reolink camera's."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ReolinkOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors["host"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=80): cv.positive_int,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


async def validate_input(hass: core.HomeAssistant, user_input: dict):
    """Validate the user input allows us to connect."""
    base = ReolinkBase(
        hass,
        user_input[CONF_HOST],
        user_input[CONF_PORT],
        user_input[CONF_USERNAME],
        user_input[CONF_PASSWORD],
    )

    if not await base.connect_api():
        raise CannotConnect

    title = base.api.name
    base.disconnect_api()
    return {"title": title}


class ReolinkOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Reolink options."""

    def __init__(self, config_entry):
        """Initialize Reolink options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.base = None

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        """Manage the Reolink options."""
        self.base = self.hass.data[DOMAIN][self.config_entry.entry_id][BASE]

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STREAM, default=self.base.api.stream): vol.In(
                        ["main", "sub"]
                    ),
                    vol.Required(CONF_PROTOCOL, default=self.base.api.protocol): vol.In(
                        ["rtmp", "rtsp"]
                    ),
                    vol.Required(
                        CONF_CHANNEL, default=self.base.api.channel
                    ): cv.positive_int,
                    vol.Required(
                        CONF_MOTION_OFF_DELAY, default=self.base.motion_off_delay
                    ): cv.positive_int,
                }
            ),
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
