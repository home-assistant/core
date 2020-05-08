"""Config flow to configure Blink."""
from datetime import timedelta
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


def validate_input(data):
    """Validate the scan interval."""
    try:
        return timedelta(seconds=data[CONF_SCAN_INTERVAL])
    except TypeError:
        return data[CONF_SCAN_INTERVAL]


class BlinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Blink config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the blink flow."""
        self.blink = None

    def step_user(self, user_input=None):
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
            user_input[CONF_SCAN_INTERVAL] = validate_input(user_input)
            self.async_set_unique_id(user_input[CONF_USERNAME])
            self.blink = blinkpy.Blink(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                motion_interval=DEFAULT_OFFSET,
                legacy_subdomain=False,
                no_prompt=True,
                device_id="Home Assistant",
            )
            self.blink.refresh_rate = user_input[CONF_SCAN_INTERVAL].total_seconds()

            self.blink.start()

            if not self.blink.key_required:
                # No key required, we're good
                return self.async_create_entry(
                    title=DOMAIN,
                    data={
                        CONF_USERNAME: user_input["username"],
                        CONF_PASSWORD: user_input["password"],
                        CONF_SCAN_INTERVAL: user_input["scan_interval"],
                    },
                )
            return self.step_2fa()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=stored_username): str,
                    vol.Required(CONF_PASSWORD, default=stored_password): str,
                    vol.Optional(CONF_SCAN_INTERVAL, default=stored_interval): int,
                }
            ),
            errors={},
        )

    def step_2fa(self, user_input=None):
        """Handle 2FA step."""
        if user_input:
            pin = user_input[CONF_PIN]
            if not pin:
                pin = None
            if self.blink.login_handler.send_auth_key(self.blink, pin):
                self.blink.setup_post_verify()
                blink_data = self.blink.login_handler.data
                return self.async_create_entry(
                    title=DOMAIN,
                    data={
                        CONF_USERNAME: blink_data["username"],
                        CONF_PASSWORD: blink_data["password"],
                        CONF_SCAN_INTERVAL: self.blink.refresh_rate,
                    },
                )

        return self.async_show_form(
            step_id="2fa", data_schema=vol.Schema({vol.Optional(CONF_PIN): str}),
        )

    async def async_step_import(self, import_data):
        """Import blink config from configuration.yaml."""
        return await self.hass.async_add_executor_job(self.step_user(import_data))
