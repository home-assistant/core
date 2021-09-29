"""Config flow for Switchbot."""
from __future__ import annotations

from asyncio import Lock
import logging
from typing import Any

from switchbot import GetSwitchbotDevices  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_SENSOR_TYPE
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    BTLE_LOCK,
    CONF_RETRY_COUNT,
    CONF_RETRY_TIMEOUT,
    CONF_SCAN_TIMEOUT,
    CONF_TIME_BETWEEN_UPDATE_COMMAND,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_TIMEOUT,
    DEFAULT_SCAN_TIMEOUT,
    DEFAULT_TIME_BETWEEN_UPDATE_COMMAND,
    DOMAIN,
    SUPPORTED_MODEL_TYPES,
)

_LOGGER = logging.getLogger(__name__)


def _btle_connect() -> dict:
    """Scan for BTLE advertisement data."""

    switchbot_devices = GetSwitchbotDevices().discover()

    if not switchbot_devices:
        raise NotConnectedError("Failed to discover switchbot")

    return switchbot_devices


class SwitchbotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Switchbot."""

    VERSION = 1

    async def _get_switchbots(self) -> dict:
        """Try to discover nearby Switchbot devices."""
        # asyncio.lock prevents btle adapter exceptions if there are multiple calls to this method.
        # store asyncio.lock in hass data if not present.
        if DOMAIN not in self.hass.data:
            self.hass.data.setdefault(DOMAIN, {})
        if BTLE_LOCK not in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][BTLE_LOCK] = Lock()

        connect_lock = self.hass.data[DOMAIN][BTLE_LOCK]

        # Discover switchbots nearby.
        async with connect_lock:
            _btle_adv_data = await self.hass.async_add_executor_job(_btle_connect)

        return _btle_adv_data

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SwitchbotOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SwitchbotOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the config flow."""
        self._discovered_devices = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""

        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_MAC].replace(":", ""))
            self._abort_if_unique_id_configured()

            user_input[CONF_SENSOR_TYPE] = SUPPORTED_MODEL_TYPES[
                self._discovered_devices[self.unique_id]["modelName"]
            ]

            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        try:
            self._discovered_devices = await self._get_switchbots()

        except NotConnectedError:
            return self.async_abort(reason="cannot_connect")

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        # Get devices already configured.
        configured_devices = {
            item.data[CONF_MAC]
            for item in self._async_current_entries(include_ignore=False)
        }

        # Get supported devices not yet configured.
        unconfigured_devices = {
            device["mac_address"]: f"{device['mac_address']} {device['modelName']}"
            for device in self._discovered_devices.values()
            if device["modelName"] in SUPPORTED_MODEL_TYPES
            and device["mac_address"] not in configured_devices
        }

        if not unconfigured_devices:
            return self.async_abort(reason="no_unconfigured_devices")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_MAC): vol.In(unconfigured_devices),
                vol.Required(CONF_NAME): str,
                vol.Optional(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
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

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Switchbot options."""
        if user_input is not None:
            # Update common entity options for all other entities.
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.unique_id != self.config_entry.unique_id:
                    self.hass.config_entries.async_update_entry(
                        entry, options=user_input
                    )
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
