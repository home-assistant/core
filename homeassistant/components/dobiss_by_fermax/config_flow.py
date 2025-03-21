"""Config flow for dobiss integration."""
import logging

import dobissapi
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.const import __version__ as HAVERSION  # noqa
from awesomeversion import AwesomeVersion
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_COVER_CLOSETIME,
    CONF_COVER_SET_END_POSITION,
    CONF_COVER_USE_TIMED,
    CONF_IGNORE_ZIGBEE_DEVICES,
    CONF_INVERT_BINARY_SENSOR,
    CONF_SECRET,
    CONF_SECURE,
    CONF_WEBSOCKET_TIMEOUT,
    DEFAULT_COVER_CLOSETIME,
    DEFAULT_COVER_SET_END_POSITION,
    DEFAULT_COVER_USE_TIMED,
    DEFAULT_IGNORE_ZIGBEE_DEVICES,
    DEFAULT_INVERT_BINARY_SENSOR,
    DEFAULT_WEBSOCKET_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

HA_VERSION = AwesomeVersion(HAVERSION)

class DobissConnection:
    """setup connection to dobiss nxt server."""

    def __init__(self, secret, host, secure):
        """Initialize."""
        self.secret = secret
        self.host = host
        self.secure = secure

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        response = False
        dobiss = dobissapi.DobissAPI(self.secret, self.host, self.secure)
        try:
            if await dobiss.auth_check():
                response = True
        except Exception:
            _LOGGER.exception("Dobiss authentication failed")
        return response


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    hub = DobissConnection(data[CONF_SECRET], data[CONF_HOST], data[CONF_SECURE])

    if not await hub.authenticate():
        raise InvalidAuth

    return {"title": f"NXT server {data[CONF_HOST]}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for dobiss."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return DobissOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors[CONF_HOST] = "cannot_connect"
            except InvalidAuth:
                errors[CONF_SECRET] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        else:
            user_input = {}

        secure = False
        if CONF_SECURE in user_input:
            secure = user_input.get(CONF_SECURE)
        fields = {}
        fields[vol.Required(CONF_SECRET, default=user_input.get(CONF_SECRET))] = str
        fields[vol.Required(CONF_HOST, default=user_input.get(CONF_HOST))] = str
        fields[vol.Optional(CONF_SECURE, default=secure)] = bool

        # show the form if there were errors or at the first run
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class DobissOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        if HA_VERSION < '2024.12':
            self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_COVER_SET_END_POSITION,
                    default=self.config_entry.options.get(
                        CONF_COVER_SET_END_POSITION, DEFAULT_COVER_SET_END_POSITION
                    ),
                ): cv.boolean,
                vol.Required(
                    CONF_INVERT_BINARY_SENSOR,
                    default=self.config_entry.options.get(
                        CONF_INVERT_BINARY_SENSOR, DEFAULT_INVERT_BINARY_SENSOR
                    ),
                ): cv.boolean,
                vol.Required(
                    CONF_IGNORE_ZIGBEE_DEVICES,
                    default=self.config_entry.options.get(
                        CONF_IGNORE_ZIGBEE_DEVICES, DEFAULT_IGNORE_ZIGBEE_DEVICES
                    ),
                ): cv.boolean,
                vol.Required(
                    CONF_COVER_CLOSETIME,
                    default=self.config_entry.options.get(
                        CONF_COVER_CLOSETIME, DEFAULT_COVER_CLOSETIME
                    ),
                ): cv.positive_int,
                vol.Optional(
                    CONF_COVER_USE_TIMED,
                    default=self.config_entry.options.get(
                        CONF_COVER_USE_TIMED, DEFAULT_COVER_USE_TIMED
                    ),
                ): cv.boolean,
                vol.Required(
                    CONF_WEBSOCKET_TIMEOUT,
                    default=self.config_entry.options.get(
                        CONF_WEBSOCKET_TIMEOUT, DEFAULT_WEBSOCKET_TIMEOUT
                    ),
                ): cv.positive_int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
