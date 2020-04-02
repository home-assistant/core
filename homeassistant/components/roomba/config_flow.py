"""Config flow to configure roomba component."""
import logging

from roomba import Roomba
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from . import CannotConnect, InvalidAuth, async_connect_or_timeout
from .const import (
    CONF_CERT,
    CONF_CONTINUOUS,
    CONF_DELAY,
    DEFAULT_CERT,
    DEFAULT_CONTINUOUS,
    DEFAULT_DELAY,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_CERT, default=DEFAULT_CERT): str,
        vol.Optional(CONF_CONTINUOUS, default=DEFAULT_CONTINUOUS): bool,
        vol.Optional(CONF_DELAY, default=DEFAULT_DELAY): int,
    }
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    roomba = Roomba(
        address=data[CONF_HOST],
        blid=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        cert_name=data[CONF_CERT],
        continuous=data[CONF_CONTINUOUS],
        delay=data[CONF_DELAY],
    )

    await async_connect_or_timeout(hass, roomba)


class RoombaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Roomba configuration flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""
        return await self.async_step_user(import_info)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors = {"base": "cannot_connect"}
            except Exception:  # pylint: disable=broad-except
                errors = {"base": "unknown"}

            if "base" not in errors:
                return self.async_create_entry(
                    title=validated_input["title"], data=user_input
                )

        # If there was no user input, do not show the errors.
        if user_input is None:
            errors = {}

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CERT,
                        default=self.config_entry.options.get(CONF_CERT, DEFAULT_CERT),
                    ): str,
                    vol.Optional(
                        CONF_CONTINUOUS,
                        default=self.config_entry.options.get(
                            CONF_CONTINUOUS, DEFAULT_CONTINUOUS
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_DELAY,
                        default=self.config_entry.options.get(
                            CONF_DELAY, DEFAULT_DELAY
                        ),
                    ): int,
                }
            ),
        )
