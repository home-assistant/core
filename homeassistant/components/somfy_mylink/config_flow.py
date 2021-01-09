"""Config flow for Somfy MyLink integration."""
import asyncio
import logging

from somfy_mylink_synergy import SomfyMyLinkSynergy
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import CONF_SYSTEM_ID
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SYSTEM_ID): str,
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=44100): str,
    }
)

# options
# vol.Optional(CONF_DEFAULT_REVERSE, default=False): cv.boolean,
# vol.Optional(CONF_ENTITY_CONFIG, default={}): validate_entity_config,


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    system_id = data[CONF_SYSTEM_ID]

    somfy_mylink = SomfyMyLinkSynergy(system_id, host, port)

    try:
        status_info = await somfy_mylink.status_info()
    except asyncio.TimeoutError:
        raise CannotConnect

    _LOGGER.error("status_info: %s", status_info)

    if not status_info:
        raise InvalidAuth

    return {"title": f"MyLink {system_id}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Somfy MyLink."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_ASSUMED

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        if self._host_already_configured(user_input[CONF_HOST]):
            return self.async_abort(reason="already_configured")

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        if self._host_already_configured(user_input[CONF_HOST]):
            return self.async_abort(reason="already_configured")

        return await self.async_step_user(user_input)

    def _host_already_configured(self, host):
        """See if we already have an entry matching the host."""
        for entry in self._async_current_entries():
            if CONF_HOST not in entry.data:
                continue

            if entry.data[CONF_HOST] == host:
                return True
        return False


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
