"""Config flow for Bose Soundtouch integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .media_player import DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)


class SoundtouchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bose SoundTouch."""

    VERSION = 1

    def __init__(self):
        """Initialize a new SoundtouchConfigFlow."""
        self.name = None
        self.host = None
        self.port = None

    async def async_step_user(self, user_input=None):
        """Handle a config flow for Bose Soundtouch."""
        if user_input is not None:
            self.name = user_input[CONF_NAME]
            self.host = user_input[CONF_HOST]
            self.port = user_input[CONF_PORT]
            return await self.async_step_confirm()
        return self.async_show_form(
            step_id="user",
            last_step=True,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                }
            ),
            description_placeholders={CONF_NAME: self.name},
        )

    async def async_step_zeroconf(self, discovery_info):
        """Handle zeroconf config flow for Bose Soundtouch."""
        mac = discovery_info["properties"]["MAC"]
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()

        name = discovery_info["name"].split(".")[0]
        self.context["identifier"] = self.unique_id
        self.context["host"] = discovery_info["host"]
        self.context["port"] = discovery_info["port"]
        self.context["title_placeholders"] = {"name": name}
        self.name = name
        self.host = discovery_info[CONF_HOST]
        self.port = discovery_info[CONF_PORT]
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            data = {
                CONF_NAME: self.name,
                CONF_HOST: self.host,
                CONF_PORT: self.port,
            }
            return self.async_create_entry(title=self.name, data=data)
        return self.async_show_form(
            step_id="confirm",
            last_step=True,
            description_placeholders={CONF_NAME: self.name},
        )
