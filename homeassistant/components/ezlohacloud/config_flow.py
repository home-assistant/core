import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN
from .options_flow import EzloOptionsFlowHandler  # Import options flow

_LOGGER = logging.getLogger(__name__)


class EzloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Ezlo HA Cloud."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input=None):
        # """Initial setup form."""
        errors = {}

        if user_input is not None:
            try:
                await self.async_set_unique_id("user_authentication")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Ezlo HA Cloud", data=user_input)
            except config_entries.ConfigEntryError:
                errors["base"] = "already_configured"
            except Exception as e:  # noqa: BLE001
                errors["base"] = str(e)

        data_schema = vol.Schema(
            {
                vol.Required("sni_host"): str,
                vol.Required("sni_port"): int,
                vol.Required("end_host"): str,
                vol.Required("end_port"): int,
                vol.Required("fernet_token"): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Enable the 'Configure' and 'Login' buttons in the UI."""
        return EzloOptionsFlowHandler()
