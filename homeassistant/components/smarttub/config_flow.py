"""Config flow to configure the SmartTub integration."""
import logging

from smarttub import LoginFailed
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN  # pylint: disable=unused-import
from .controller import SmartTubController

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
)


_LOGGER = logging.getLogger(__name__)


class SmartTubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """SmartTub configuration flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        controller = SmartTubController(self.hass)
        try:
            account = await controller.login(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
        except LoginFailed:
            errors["base"] = "invalid_auth"
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        existing_entry = await self.async_set_unique_id(account.id)
        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=user_input)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(title=user_input[CONF_EMAIL], data=user_input)
