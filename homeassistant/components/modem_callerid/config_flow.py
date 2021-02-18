"""Config flow for Modem Caller ID integration."""
from phone_modem import PhoneModem, exceptions
import serial
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE, CONF_NAME

from . import _LOGGER
from .const import DEFAULT_DEVICE, DEFAULT_NAME
from .const import DOMAIN  # pylint:disable=unused-import

DATA_SCHEMA = vol.Schema({"name": str, "device": str})


class PhoneModemFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Phone Modem."""

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            name = user_input[CONF_NAME]
            device = user_input[CONF_DEVICE]

            if await self._async_endpoint_existed(device):
                return self.async_abort(reason="already_configured")

            try:
                api = PhoneModem(device)  # noqa pylint:disable=unused-variable

            except (
                FileNotFoundError,
                exceptions.SerialError,
                serial.SerialException,
                serial.serialutil.SerialException,
            ):
                errors["base"] = "cannot_connect"
                _LOGGER.error("Unable to open port %s", device)
            else:
                return self.async_create_entry(
                    title=name,
                    data={CONF_NAME: name, CONF_DEVICE: device},
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME, default=user_input.get(CONF_NAME) or DEFAULT_NAME
                    ): str,
                    vol.Optional(
                        CONF_DEVICE,
                        default=user_input.get(CONF_DEVICE) or DEFAULT_DEVICE,
                    ): str,
                }
            ),
            errors=errors,
        )

    async def _async_endpoint_existed(self, endpoint):
        for entry in self._async_current_entries():
            if endpoint == entry.data.get(CONF_DEVICE):
                return True
        return False

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            _LOGGER.warning("Already configured. Only a single configuration possible.")
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_user(import_config)
