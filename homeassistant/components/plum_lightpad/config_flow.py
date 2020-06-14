"""Config flow for Plum Lightpad."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import ConfigType

from .const import DOMAIN
from .utils import load_plum

_LOGGER = logging.getLogger(__name__)


class PlumLightpadConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Plum Lightpad integration."""

    VERSION = 1

    async def async_step_user(self, user_input: Optional[ConfigType]) -> Dict[str, Any]:
        """Handle a flow initialized by the user or redirected to by import."""
        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_USERNAME): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
            )

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        # load Plum just so we know username/password work
        plum = await load_plum(username, password, self.hass)
        plum.cleanup()

        already_registered = await self.async_set_unique_id(username)
        if already_registered:
            _LOGGER.warning(
                "Config entry with ID = %s is already registered, skipping...",
                self.unique_id,
            )
            return self.async_abort(reason="single_instance_per_username_allowed")

        return self.async_create_entry(
            title=username, data={CONF_USERNAME: username, CONF_PASSWORD: password}
        )

    async def async_step_import(
        self, import_config: Optional[ConfigType]
    ) -> Dict[str, Any]:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)
