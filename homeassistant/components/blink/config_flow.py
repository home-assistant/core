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
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_OFFSET, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class BlinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Blink config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the blink flow."""
        self.blink = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="one_instance_only")

        stored_username = ""
        stored_password = ""
        stored_interval = DEFAULT_SCAN_INTERVAL

        if DOMAIN in self.hass.data:
            stored_username = self.hass.data[DOMAIN].get(CONF_USERNAME)
            stored_password = self.hass.data[DOMAIN].get(CONF_PASSWORD)
            stored_interval = self.hass.data[DOMAIN].get(CONF_SCAN_INTERVAL)

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self.blink = blinkpy.Blink(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                motion_interval=DEFAULT_OFFSET,
                legacy_subdomain=False,
                no_prompt=True,
                device_id="Home Assistant",
            )
            self.blink.refresh_rate = user_input[CONF_SCAN_INTERVAL].total_seconds()

            await self.hass.async_add_executor_job(self._blink.start())

            if not self.blink.key_required:
                # No key required, we're good
                return await self.async_create_entry(
                    title=DOMAIN,
                    data={CONF_USERNAME: self.blink.login_handler.data["username"]},
                )

            return await self.async_step_2fa()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=stored_username): cv.string,
                    vol.Required(CONF_PASSWORD, default=stored_password): cv.string,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=stored_interval
                    ): cv.time_period,
                }
            ),
            errors={},
        )

    async def async_step_2fa(self, user_input=None):
        """Handle 2FA step."""
        if user_input:
            await self.hass.async_add_executor_job(self.blink.setup_post_verify())
            return await self.async_create_entry(
                title=DOMAIN,
                data={CONF_USERNAME: self.blink.login_handler.data["username"]},
            )

        return self.async_show_form(
            step_id="2FA", data_schema=vol.Schema({CONF_PIN: str})
        )

    async def async_step_import(self, import_data):
        """Import blink config from configuration.yaml."""
        return await self.async_step_user(import_data)
