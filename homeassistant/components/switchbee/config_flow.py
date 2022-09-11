"""Config flow for SwitchBee Smart Home integration."""
from __future__ import annotations

import logging
from typing import Any

from switchbee.api import CentralUnitAPI, SwitchBeeError
from switchbee.device import DeviceType
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_DEFUALT_ALLOWED, CONF_DEVICES, CONF_SWITCHES_AS_LIGHTS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_SWITCHES_AS_LIGHTS, default=False): cv.boolean,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]):
    """Validate the user input allows us to connect."""

    websession = async_get_clientsession(hass, verify_ssl=False)
    api = CentralUnitAPI(
        data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD], websession
    )
    try:
        await api.connect()
    except SwitchBeeError as exp:
        _LOGGER.error(exp)
        if "LOGIN_FAILED" in str(exp):
            raise InvalidAuth from SwitchBeeError

        raise CannotConnect from SwitchBeeError

    return format_mac(api.mac)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SwitchBee Smart Home."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Show the setup form to the user."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        try:
            mac_formated = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        else:
            await self.async_set_unique_id(mac_formated)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for AEMET."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Handle options flow."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        all_devices = [
            DeviceType.Switch,
            DeviceType.TimedSwitch,
            DeviceType.GroupSwitch,
            DeviceType.TimedPowerSwitch,
        ]

        data_schema = {
            vol.Required(
                CONF_DEVICES,
                default=self.config_entry.options.get(
                    CONF_DEVICES,
                    CONF_DEFUALT_ALLOWED,
                ),
            ): cv.multi_select([device.display for device in all_devices]),
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(data_schema))


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
