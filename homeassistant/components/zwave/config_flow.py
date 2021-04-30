"""Config flow to configure Z-Wave."""
# pylint: disable=import-outside-toplevel
from collections import OrderedDict

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_NETWORK_KEY,
    CONF_USB_STICK_PATH,
    DEFAULT_CONF_USB_STICK_PATH,
    DOMAIN,
)


@config_entries.HANDLERS.register(DOMAIN)
class ZwaveFlowHandler(config_entries.ConfigFlow):
    """Handle a Z-Wave config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the Z-Wave config flow."""
        self.usb_path = CONF_USB_STICK_PATH

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        fields = OrderedDict()
        fields[
            vol.Required(CONF_USB_STICK_PATH, default=DEFAULT_CONF_USB_STICK_PATH)
        ] = str
        fields[vol.Optional(CONF_NETWORK_KEY)] = str

        if user_input is not None:
            # Check if USB path is valid
            from openzwave.object import ZWaveException
            from openzwave.option import ZWaveOption

            try:
                from functools import partial

                option = await self.hass.async_add_executor_job(  # noqa: F841 pylint: disable=unused-variable
                    partial(
                        ZWaveOption,
                        user_input[CONF_USB_STICK_PATH],
                        user_path=self.hass.config.config_dir,
                    )
                )
            except ZWaveException:
                errors["base"] = "option_error"
                return self.async_show_form(
                    step_id="user", data_schema=vol.Schema(fields), errors=errors
                )

            if user_input.get(CONF_NETWORK_KEY) is None:
                # Generate a random key
                from random import choice

                key = ""
                for i in range(16):
                    key += "0x"
                    key += choice("1234567890ABCDEF")
                    key += choice("1234567890ABCDEF")
                    if i < 15:
                        key += ", "
                user_input[CONF_NETWORK_KEY] = key

            return self.async_create_entry(
                title="Z-Wave",
                data={
                    CONF_USB_STICK_PATH: user_input[CONF_USB_STICK_PATH],
                    CONF_NETWORK_KEY: user_input[CONF_NETWORK_KEY],
                },
            )

        return self.async_show_form(step_id="user", data_schema=vol.Schema(fields))

    async def async_step_import(self, info):
        """Import existing configuration from Z-Wave."""
        if self._async_current_entries():
            return self.async_abort(reason="already_setup")

        return self.async_create_entry(
            title="Z-Wave (import from configuration.yaml)",
            data={
                CONF_USB_STICK_PATH: info.get(CONF_USB_STICK_PATH),
                CONF_NETWORK_KEY: info.get(CONF_NETWORK_KEY),
            },
        )
