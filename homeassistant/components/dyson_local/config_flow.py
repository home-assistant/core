"""Config flow for Dyson integration."""
from __future__ import annotations

import logging

from libdyson import (
    DEVICE_TYPE_360_EYE,
    DEVICE_TYPE_360_HEURIST,
    DEVICE_TYPE_NAMES,
    get_device,
    get_mqtt_info_from_wifi_info,
)
from libdyson.exceptions import (
    DysonException,
    DysonFailedToParseWifiInfo,
    DysonInvalidCredential,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_CREDENTIAL, CONF_DEVICE_TYPE, CONF_SERIAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 10

CONF_METHOD = "method"
CONF_SSID = "ssid"
CONF_PASSWORD = "password"

SETUP_METHODS = {
    "wifi": "Setup using WiFi information",
    "manual": "Setup manually",
}

SUPPORTED_DEVICE_TYPES = [
    DEVICE_TYPE_360_EYE,
    DEVICE_TYPE_360_HEURIST,
]
SUPPORTED_DEVICE_TYPE_NAMES = {
    device_type: name
    for device_type, name in DEVICE_TYPE_NAMES.items()
    if device_type in SUPPORTED_DEVICE_TYPES
}


class DysonLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Dyson local config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the config flow."""
        self._device_info = None

    async def async_step_user(self, user_input: dict | None = None):
        """Handle step to setup using device WiFi information."""
        errors = {}
        if user_input is not None:
            try:
                serial, credential, device_type = get_mqtt_info_from_wifi_info(
                    user_input[CONF_SSID], user_input[CONF_PASSWORD]
                )
            except DysonFailedToParseWifiInfo:
                errors["base"] = "cannot_parse_wifi_info"
            else:
                for entry in self._async_current_entries():
                    if entry.unique_id == serial:
                        return self.async_abort(reason="already_configured")
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()

                device_type_name = DEVICE_TYPE_NAMES[device_type]
                _LOGGER.debug("Successfully parse WiFi information")
                _LOGGER.debug("Serial: %s", serial)
                _LOGGER.debug("Device Type: %s", device_type)
                _LOGGER.debug("Device Type Name: %s", device_type_name)

                host = user_input[CONF_HOST]
                device = get_device(serial, credential, device_type)
                try:
                    await self.hass.async_add_executor_job(device.connect, host)
                except DysonInvalidCredential:
                    errors["base"] = "invalid_auth"
                except DysonException as err:
                    _LOGGER.debug("Failed to connect to device: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=device_type_name,
                        data={
                            CONF_SERIAL: serial,
                            CONF_CREDENTIAL: credential,
                            CONF_DEVICE_TYPE: device_type,
                            CONF_NAME: device_type_name,
                            CONF_HOST: host,
                        },
                    )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SSID, default=user_input.get(CONF_SSID, "")): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Represents connection failure."""


class CannotFind(HomeAssistantError):
    """Represents discovery failure."""


class InvalidAuth(HomeAssistantError):
    """Represents invalid authentication."""
