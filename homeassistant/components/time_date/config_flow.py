"""Config flow to configure Time and Date component."""
import logging
from typing import Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DISPLAY_OPTIONS
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN  # pylint: disable=unused-import
from .const import OPTION_TYPES

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DISPLAY_OPTIONS): cv.multi_select(OPTION_TYPES),
    },
    extra=vol.REMOVE_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


class ProximityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Proximity configuration flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(
        self, import_info: dict
    ) -> config_entries.ConfigFlow.async_step_user:
        """Set the config entry up from yaml."""
        return await self.async_step_user(import_info)

    async def async_step_user(
        self, user_input: Optional[dict] = None
    ) -> config_entries.ConfigFlow.async_show_form:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=DOMAIN, data=user_input)
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
