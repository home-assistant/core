"""Config flow to configure Blink."""
import logging

from blinkpy import blinkpy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)

from .const import DEFAULT_OFFSET, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class BlinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Blink config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the blink flow."""
        self.blink = None
        self.data = {
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        }

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is not None:
            self.data[CONF_USERNAME] = user_input["username"]
            self.data[CONF_PASSWORD] = user_input["password"]

            await self.async_set_unique_id(self.data[CONF_USERNAME])

            if CONF_SCAN_INTERVAL in user_input:
                self.data[CONF_SCAN_INTERVAL] = user_input["scan_interval"]

            try:
                self.blink = self.hass.data[DOMAIN]
            except KeyError:
                self.blink = blinkpy.Blink(
                    username=self.data[CONF_USERNAME],
                    password=self.data[CONF_PASSWORD],
                    motion_interval=DEFAULT_OFFSET,
                    legacy_subdomain=False,
                    no_prompt=True,
                    device_id="Home Assistant",
                )
                self.blink.refresh_rate = self.data[CONF_SCAN_INTERVAL]
                await self.hass.async_add_executor_job(self.blink.start)

            if not self.blink.key_required:
                # No key required, we're good
                self.hass.data[DOMAIN] = {self.unique_id: self.blink}
                return self.async_create_entry(title=DOMAIN, data=self.data,)
            return await self.async_step_2fa()

        data_schema = {
            vol.Required("username"): str,
            vol.Required("password"): str,
        }

        if self.show_advanced_options:
            data_schema[
                vol.Required("scan_interval", default=DEFAULT_SCAN_INTERVAL)
            ] = int

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors={},
        )

    async def async_step_2fa(self, user_input=None):
        """Handle 2FA step."""
        if user_input:
            pin = user_input[CONF_PIN]
            if not pin or pin.lower() == "none":
                pin = None
            if await self.hass.async_add_executor_job(
                self.blink.login_handler.send_auth_key, self.blink, pin
            ):
                await self.hass.async_add_executor_job(self.blink.setup_post_verify)
                self.hass.data[DOMAIN] = {self.unique_id: self.blink}
                return self.async_create_entry(title=DOMAIN, data=self.data,)

        return self.async_show_form(
            step_id="2fa", data_schema=vol.Schema({vol.Required("pin"): str}),
        )

    async def async_step_import(self, import_data):
        """Import blink config from configuration.yaml."""
        return await self.async_step_user(import_data)
