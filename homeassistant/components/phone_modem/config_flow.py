"""Config flow for Phone Modem integration."""
import logging

from phone_modem import PhoneModem, exceptions
import serial
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_PORT

from .const import DEFAULT_DEVICE, DEFAULT_NAME
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({"name": str, "port": str})


class PhoneModemFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Phone Modem."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            name = user_input[CONF_NAME]
            port = user_input[CONF_PORT]

            if await self._async_endpoint_existed(port):
                return self.async_abort(reason="already_configured")

            try:
                api = PhoneModem(port)  # noqa pylint:disable=unused-variable

            except (
                FileNotFoundError,
                exceptions.SerialError,
                serial.SerialException,
                serial.serialutil.SerialException,
            ):
                errors["base"] = "cannot_connect"
                _LOGGER.error("Unable to open port %s", port)
            else:
                return self.async_create_entry(
                    title=name,
                    data={CONF_NAME: name, CONF_PORT: port},
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
                        CONF_PORT,
                        default=user_input.get(CONF_PORT) or DEFAULT_DEVICE,
                    ): str,
                }
            ),
            errors=errors,
        )

    async def _async_endpoint_existed(self, endpoint):
        for entry in self._async_current_entries():
            if endpoint == entry.data.get(CONF_PORT):
                return True
        return False
