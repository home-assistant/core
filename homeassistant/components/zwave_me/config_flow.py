"""Config flow to configure ZWaveMe integration."""

import logging

from url_normalize import url_normalize
import voluptuous as vol
from zwave_me_ws import ZWaveMe

from homeassistant import config_entries

from .const import CONF_TOKEN, CONF_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZWaveMeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """ZWaveMe integration config flow."""

    def __init__(self):
        """Initialize flow."""
        self.url = vol.UNDEFINED
        self.token = vol.UNDEFINED

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user or started with zeroconf."""
        errors = {}
        if self.url == vol.UNDEFINED:
            schema = vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_TOKEN): str,
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Required(CONF_TOKEN): str,
                }
            )

        if user_input is not None:
            if self.url == vol.UNDEFINED:
                self.url = user_input["url"]

            self.token = user_input["token"]
            if not self.url.startswith(("ws://", "wss://")):
                self.url = f"ws://{self.url}"
            self.url = url_normalize(self.url, default_scheme="ws")
            if "://" not in self.url:
                errors[CONF_URL] = "invalid_url"
                self.url = vol.UNDEFINED
                return self.async_show_form(
                    step_id="user",
                    data_schema=schema,
                    errors=errors,
                )
            _LOGGER.warning("WHO")
            conn = ZWaveMe(url=self.url, token=self.token)
            _LOGGER.warning("conn")
            if await conn.get_connection():
                _LOGGER.warning("conn2")
                uuid = await conn.get_uuid()
                _LOGGER.warning("conn3 %s", uuid)
                if uuid is not None:
                    await self.async_set_unique_id(uuid + self.url)
                    _LOGGER.warning("conn4")
                    self._abort_if_unique_id_configured()
                    await conn.close_ws()
                    _LOGGER.warning("conn5")
                    return self.async_create_entry(
                        title=self.url,
                        data={"url": self.url, "token": self.token},
                    )
            errors[CONF_URL] = "could_not_retrieve_data"
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info):
        """
        Handle a discovered Z-Wave accessory - get url to pass into user step.

        This flow is triggered by the discovery component.
        """
        self.url = discovery_info.host
        return await self.async_step_user()
