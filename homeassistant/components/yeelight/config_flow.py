"""Config flow for Yeelight integration."""
import logging

import voluptuous as vol
import yeelight

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_ID, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import (
    CONF_DEVICE,
    CONF_MODE_MUSIC,
    CONF_MODEL,
    CONF_NIGHTLIGHT_SWITCH,
    CONF_NIGHTLIGHT_SWITCH_TYPE,
    CONF_SAVE_ON_CHANGE,
    CONF_TRANSITION,
    NIGHTLIGHT_SWITCH_TYPE_LIGHT,
)
from . import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yeelight."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return OptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the config flow."""
        self._capabilities = None
        self._discovered_devices = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if user_input.get(CONF_HOST):
                try:
                    await self._async_try_connect(user_input[CONF_HOST])
                    return self.async_create_entry(
                        title=self._async_default_name(),
                        data=user_input,
                    )
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except AlreadyConfigured:
                    return self.async_abort(reason="already_configured")
            else:
                return await self.async_step_pick_device()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_pick_device(self, user_input=None):
        """Handle the step to pick discovered device."""
        if user_input is not None:
            unique_id = user_input[CONF_DEVICE]
            self._capabilities = self._discovered_devices[unique_id]
            return self.async_create_entry(
                title=self._async_default_name(),
                data={CONF_ID: unique_id},
            )

        configured_devices = {
            entry.data[CONF_ID]
            for entry in self._async_current_entries()
            if entry.data[CONF_ID]
        }
        devices_name = {}
        # Run 3 times as packets can get lost
        for _ in range(3):
            devices = await self.hass.async_add_executor_job(yeelight.discover_bulbs)
            for device in devices:
                capabilities = device["capabilities"]
                unique_id = capabilities["id"]
                if unique_id in configured_devices:
                    continue  # ignore configured devices
                model = capabilities["model"]
                host = device["ip"]
                name = f"{host} {model} {unique_id}"
                self._discovered_devices[unique_id] = capabilities
                devices_name[unique_id] = name

        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    async def async_step_import(self, user_input=None):
        """Handle import step."""
        host = user_input[CONF_HOST]
        try:
            await self._async_try_connect(host)
        except CannotConnect:
            _LOGGER.error("Failed to import %s: cannot connect", host)
            return self.async_abort(reason="cannot_connect")
        except AlreadyConfigured:
            return self.async_abort(reason="already_configured")
        if CONF_NIGHTLIGHT_SWITCH_TYPE in user_input:
            user_input[CONF_NIGHTLIGHT_SWITCH] = (
                user_input.pop(CONF_NIGHTLIGHT_SWITCH_TYPE)
                == NIGHTLIGHT_SWITCH_TYPE_LIGHT
            )
        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

    async def _async_try_connect(self, host):
        """Set up with options."""
        bulb = yeelight.Bulb(host)
        try:
            capabilities = await self.hass.async_add_executor_job(bulb.get_capabilities)
            if capabilities is None:  # timeout
                _LOGGER.error("Failed to get capabilities from %s: timeout", host)
                raise CannotConnect
        except OSError as err:
            _LOGGER.error("Failed to get capabilities from %s: %s", host, err)
            raise CannotConnect from err
        _LOGGER.debug("Get capabilities: %s", capabilities)
        self._capabilities = capabilities
        await self.async_set_unique_id(capabilities["id"])
        self._abort_if_unique_id_configured()

    @callback
    def _async_default_name(self):
        model = self._capabilities["model"]
        unique_id = self._capabilities["id"]
        return f"yeelight_{model}_{unique_id}"


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Yeelight."""

    def __init__(self, config_entry):
        """Initialize the option flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            # keep the name from imported entries
            options = {
                CONF_NAME: self._config_entry.options.get(CONF_NAME),
                **user_input,
            }
            return self.async_create_entry(title="", data=options)

        options = self._config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_MODEL, default=options[CONF_MODEL]): str,
                    vol.Required(
                        CONF_TRANSITION,
                        default=options[CONF_TRANSITION],
                    ): cv.positive_int,
                    vol.Required(
                        CONF_MODE_MUSIC, default=options[CONF_MODE_MUSIC]
                    ): bool,
                    vol.Required(
                        CONF_SAVE_ON_CHANGE,
                        default=options[CONF_SAVE_ON_CHANGE],
                    ): bool,
                    vol.Required(
                        CONF_NIGHTLIGHT_SWITCH,
                        default=options[CONF_NIGHTLIGHT_SWITCH],
                    ): bool,
                }
            ),
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Indicate the ip address is already configured."""
