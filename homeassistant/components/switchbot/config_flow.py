"""Config flow for Switchbot."""
from __future__ import annotations

from asyncio import Lock
import logging

from switchbot import GetSwitchbotDevices  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_SENSOR_TYPE
from homeassistant.core import callback

from .const import (
    ATTR_BOT,
    CONF_RETRY_COUNT,
    CONF_RETRY_TIMEOUT,
    CONF_SCAN_TIMEOUT,
    CONF_TIME_BETWEEN_UPDATE_COMMAND,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_TIMEOUT,
    DEFAULT_SCAN_TIMEOUT,
    DEFAULT_TIME_BETWEEN_UPDATE_COMMAND,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
CONNECT_LOCK = Lock()


def _btle_connect(mac) -> dict | None:
    """Scan for BTLE advertisement data."""
    # Try to find switchbot mac in nearby devices,
    # by scanning for btle devices.

    switchbots = GetSwitchbotDevices()
    switchbots.discover()
    switchbot_device = switchbots.get_device_data(mac=mac)

    if not switchbot_device:
        raise NotConnectedError("Failed to discover switchbot")

    return switchbot_device


class SwitchbotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Switchbot."""

    VERSION = 1

    async def _validate_mac(self, data) -> None:
        """Try to connect to Switchbot device and create entry if successful."""
        await self.async_set_unique_id(data[CONF_MAC].replace(":", ""))
        self._abort_if_unique_id_configured()

        # Validate bluetooth device mac.
        # CONNECT_LOCK prevents btle adapter exceptions if there are multiple calls to this method.
        try:
            async with CONNECT_LOCK:
                _btle_adv_data = await self.hass.async_add_executor_job(
                    _btle_connect, data[CONF_MAC]
                )

        except NotConnectedError as err:
            raise NotConnectedError(err) from err

        if _btle_adv_data["modelName"] == "WoHand":
            data[CONF_SENSOR_TYPE] = ATTR_BOT
            return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_abort(reason="switchbot_unsupported_type")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> None:
        """Get the options flow for this handler."""
        return SwitchbotOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None) -> None:
        """Handle a flow initiated by the user."""

        errors = {}

        if user_input is not None:
            user_input[CONF_MAC] = user_input[CONF_MAC].replace("-", ":").lower()

            # abort if already configured.
            for item in self._async_current_entries():
                if item.data.get(CONF_MAC) == user_input[CONF_MAC]:
                    return self.async_abort(reason="already_configured_device")

            try:
                return await self._validate_mac(user_input)

            except NotConnectedError:
                errors["base"] = "cannot_connect"

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Required(CONF_MAC): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, import_config) -> None:
        """Handle config import from yaml."""
        _LOGGER.debug("import config: %s", import_config)

        import_config[CONF_MAC] = import_config[CONF_MAC].replace("-", ":").lower()

        await self.async_set_unique_id(import_config[CONF_MAC].replace(":", ""))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=import_config[CONF_NAME], data=import_config
        )


class SwitchbotOptionsFlowHandler(OptionsFlow):
    """Handle Switchbot options."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> None:
        """Manage Switchbot options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_TIME_BETWEEN_UPDATE_COMMAND,
                default=self.config_entry.options.get(
                    CONF_TIME_BETWEEN_UPDATE_COMMAND,
                    DEFAULT_TIME_BETWEEN_UPDATE_COMMAND,
                ),
            ): int,
            vol.Optional(
                CONF_RETRY_COUNT,
                default=self.config_entry.options.get(
                    CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT
                ),
            ): int,
            vol.Optional(
                CONF_RETRY_TIMEOUT,
                default=self.config_entry.options.get(
                    CONF_RETRY_TIMEOUT, DEFAULT_RETRY_TIMEOUT
                ),
            ): int,
            vol.Optional(
                CONF_SCAN_TIMEOUT,
                default=self.config_entry.options.get(
                    CONF_SCAN_TIMEOUT, DEFAULT_SCAN_TIMEOUT
                ),
            ): int,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


class NotConnectedError(Exception):
    """Exception for unable to find device."""
