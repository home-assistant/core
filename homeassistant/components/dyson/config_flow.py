"""Config flow for Dyson integration."""
import logging

from libpurecool.dyson import DysonAccount
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICES,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import callback

from . import CONF_LANGUAGE
from . import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

CONF_ACTION = "action"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_IP = "device_ip"


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    dyson_account = DysonAccount(
        data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_LANGUAGE]
    )
    if not await hass.async_add_executor_job(dyson_account.login):
        raise InvalidAuth


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dyson."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow handler."""
        return OptionsFlowHandler(config_entry)

    async def _async_step_common(self, user_input):
        username = user_input[CONF_USERNAME]
        language = user_input[CONF_LANGUAGE]
        if any(
            entry.data[CONF_USERNAME] == username
            and entry.data[CONF_LANGUAGE] == language
            for entry in self._async_current_entries()
        ):
            return self.async_abort(reason="already_configured")
        await self.async_set_unique_id(f"{language}_{username}")
        self._abort_if_unique_id_configured()

        await validate_input(self.hass, user_input)
        return self.async_create_entry(
            title=f"{username} ({language})",
            data=user_input,
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                return await self._async_step_common(user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                    vol.Required(
                        CONF_LANGUAGE, default=user_input.get(CONF_LANGUAGE, "")
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input=None):
        """Handle the import step."""
        try:
            conf_devices = user_input.get(CONF_DEVICES, [])
            data_devices = {}
            for device in conf_devices:
                data_devices[device[CONF_DEVICE_ID]] = device[CONF_DEVICE_IP]
            user_input[CONF_DEVICES] = data_devices
            return await self._async_step_common(user_input)
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a options flow for Dyson."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize the flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            if user_input[CONF_ACTION] == "add":
                return await self.async_step_add()
            return await self.async_step_remove()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACTION): vol.In(
                        {
                            "add": "Add a new device",
                            "remove": "Remove an existed device",
                        }
                    )
                }
            ),
        )

    async def async_step_add(self, user_input=None):
        """Handle the step to add a new device."""
        if user_input is not None:
            options = {**self._config_entry.options}
            options[user_input[CONF_DEVICE]] = user_input[CONF_IP_ADDRESS]
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="add",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): vol.In(
                        [
                            serial
                            for serial, ip_addr in self._config_entry.options.items()
                            if ip_addr == ""
                        ]
                    ),
                    vol.Required(CONF_IP_ADDRESS): str,
                }
            ),
        )

    async def async_step_remove(self, user_input=None):
        """Handle the step to remove an existed device."""
        if user_input is not None:
            options = {**self._config_entry.options}
            options[user_input[CONF_DEVICE]] = ""
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="remove",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): vol.In(
                        [
                            serial
                            for serial, ip_addr in self._config_entry.options.items()
                            if ip_addr != ""
                        ]
                    )
                }
            ),
        )


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
