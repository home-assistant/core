"""Config flow to configure the Nuki integration."""

from pynuki import NukiBridge
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN

from .const import (  # pylint: disable=unused-import
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Required(CONF_TOKEN): str,
    }
)


async def validate_input(hass, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    bridge = await hass.async_add_executor_job(
        NukiBridge,
        data[CONF_HOST],
        data[CONF_TOKEN],
        data[CONF_PORT],
        True,
        DEFAULT_TIMEOUT,
    )

    try:
        info = bridge.info()
    except RequestException as err:
        raise exceptions.HomeAssistantError from err

    return info


class NukiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Nuki config flow."""

    async def async_step_import(self, user_input=None):
        """Handle a flow initiated by import."""
        return await self.async_step_init(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input):
        """Handle init step of a flow."""

        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except RequestException:
                errors["base"] = "cannot_connect"

            if "base" not in errors:
                await self.async_set_unique_id(info["ids"]["hardwareId"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["ids"]["hardwareId"], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )
