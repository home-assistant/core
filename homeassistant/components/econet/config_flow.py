"""Config flow for Gogogate2."""
import logging

from pyeconet.errors import InvalidCredentialsError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_IMPORT, ConfigFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .common import async_get_api_from_data
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class EconetFlowHandler(ConfigFlow, domain=DOMAIN):
    """Econet config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, config_data: dict = None):
        """Handle importing of configuration."""
        result = await self.async_step_user(config_data)
        self._abort_if_unique_id_configured()
        return result

    async def async_step_user(self, user_input: dict = None):
        """Handle user initiated flow."""
        user_input = user_input or {}
        errors = {}

        if user_input:
            try:
                await async_get_api_from_data(user_input)
            except InvalidCredentialsError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "cannot_connect"

            if not errors:
                return await self.async_finish(user_input)

            if self.source == SOURCE_IMPORT:
                return self.async_abort(reason=errors["base"])

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EMAIL, default=user_input.get(CONF_EMAIL, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_finish(self, user_input: dict) -> dict:
        """Finish setup."""
        await self.async_set_unique_id(user_input[CONF_EMAIL])
        return self.async_create_entry(title=user_input[CONF_EMAIL], data=user_input)
