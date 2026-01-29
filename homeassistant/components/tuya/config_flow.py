"""Config flow for Tuya."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from tuya_sharing import LoginControl
import voluptuous as vol

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    selector,
)

from . import TuyaConfigEntry
from .const import (
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
    OPTION_ENTRY_COVER_POSITION_REVERSED,
    OPTION_ENTRY_DEVICE_OPTIONS,
    TUYA_CLIENT_ID,
    TUYA_RESPONSE_CODE,
    TUYA_RESPONSE_MSG,
    TUYA_RESPONSE_QR_CODE,
    TUYA_RESPONSE_RESULT,
    TUYA_RESPONSE_SUCCESS,
    TUYA_SCHEMA,
)

_INPUT_ENTRY_CLEAR_DEVICE_OPTIONS = "clear_device_options"
_INPUT_ENTRY_DEVICE_SELECTION = "device_selection"


class TuyaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Tuya config flow."""

    __user_code: str
    __qr_code: str

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.__login_control = LoginControl()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step user."""
        errors = {}
        placeholders = {}

        if user_input is not None:
            success, response = await self.__async_get_qr_code(
                user_input[CONF_USER_CODE]
            )
            if success:
                return await self.async_step_scan()

            errors["base"] = "login_error"
            placeholders = {
                TUYA_RESPONSE_MSG: response.get(TUYA_RESPONSE_MSG, "Unknown error"),
                TUYA_RESPONSE_CODE: response.get(TUYA_RESPONSE_CODE, "0"),
            }
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USER_CODE, default=user_input.get(CONF_USER_CODE, "")
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step scan."""
        if user_input is None:
            return self.async_show_form(
                step_id="scan",
                data_schema=vol.Schema(
                    {
                        vol.Optional("QR"): selector.QrCodeSelector(
                            config=selector.QrCodeSelectorConfig(
                                data=f"tuyaSmart--qrLogin?token={self.__qr_code}",
                                scale=5,
                                error_correction_level=selector.QrErrorCorrectionLevel.QUARTILE,
                            )
                        )
                    }
                ),
            )

        ret, info = await self.hass.async_add_executor_job(
            self.__login_control.login_result,
            self.__qr_code,
            TUYA_CLIENT_ID,
            self.__user_code,
        )
        if not ret:
            # Try to get a new QR code on failure
            await self.__async_get_qr_code(self.__user_code)
            return self.async_show_form(
                step_id="scan",
                errors={"base": "login_error"},
                data_schema=vol.Schema(
                    {
                        vol.Optional("QR"): selector.QrCodeSelector(
                            config=selector.QrCodeSelectorConfig(
                                data=f"tuyaSmart--qrLogin?token={self.__qr_code}",
                                scale=5,
                                error_correction_level=selector.QrErrorCorrectionLevel.QUARTILE,
                            )
                        )
                    }
                ),
                description_placeholders={
                    TUYA_RESPONSE_MSG: info.get(TUYA_RESPONSE_MSG, "Unknown error"),
                    TUYA_RESPONSE_CODE: info.get(TUYA_RESPONSE_CODE, 0),
                },
            )

        entry_data = {
            CONF_USER_CODE: self.__user_code,
            CONF_TOKEN_INFO: {
                "t": info["t"],
                "uid": info["uid"],
                "expire_time": info["expire_time"],
                "access_token": info["access_token"],
                "refresh_token": info["refresh_token"],
            },
            CONF_TERMINAL_ID: info[CONF_TERMINAL_ID],
            CONF_ENDPOINT: info[CONF_ENDPOINT],
        }

        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data=entry_data,
            )

        return self.async_create_entry(
            title=info.get("username"),
            data=entry_data,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with Tuya."""
        if CONF_USER_CODE in entry_data:
            success, _ = await self.__async_get_qr_code(entry_data[CONF_USER_CODE])
            if success:
                return await self.async_step_scan()

        return await self.async_step_reauth_user_code()

    async def async_step_reauth_user_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with a Tuya."""
        errors = {}
        placeholders = {}

        if user_input is not None:
            success, response = await self.__async_get_qr_code(
                user_input[CONF_USER_CODE]
            )
            if success:
                return await self.async_step_scan()

            errors["base"] = "login_error"
            placeholders = {
                TUYA_RESPONSE_MSG: response.get(TUYA_RESPONSE_MSG, "Unknown error"),
                TUYA_RESPONSE_CODE: response.get(TUYA_RESPONSE_CODE, "0"),
            }
        else:
            user_input = {}

        return self.async_show_form(
            step_id="reauth_user_code",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USER_CODE, default=user_input.get(CONF_USER_CODE, "")
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def __async_get_qr_code(self, user_code: str) -> tuple[bool, dict[str, Any]]:
        """Get the QR code."""
        response = await self.hass.async_add_executor_job(
            self.__login_control.qr_code,
            TUYA_CLIENT_ID,
            TUYA_SCHEMA,
            user_code,
        )
        if success := response.get(TUYA_RESPONSE_SUCCESS, False):
            self.__user_code = user_code
            self.__qr_code = response[TUYA_RESPONSE_RESULT][TUYA_RESPONSE_QR_CODE]
        return success, response

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: TuyaConfigEntry,
    ) -> TuyaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return TuyaOptionsFlowHandler(config_entry)


class TuyaOptionsFlowHandler(OptionsFlowWithReload):
    """Handle Tuya Config options."""

    configurable_devices: dict[str, str]
    """Mapping of the configurable devices.

        `key`: friendly name
        `value`: tuya id
    """
    devices_to_configure: dict[str, str]
    """Mapping of the devices selected for configuration.

        `key`: friendly name
        `value`: tuya id
    """
    current_device: str
    """Friendly name of the currently selected device."""

    def __init__(self, config_entry: TuyaConfigEntry) -> None:
        """Initialize options flow."""
        self.options = deepcopy(dict(config_entry.options))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        self.configurable_devices = {
            self._get_device_friendly_name(device_entry): self._get_device_product_id(
                device_entry
            )
            for device_entry in dr.async_entries_for_config_entry(
                device_registry, self.config_entry.entry_id
            )
            if any(
                entity_entry.domain == COVER_DOMAIN
                for entity_entry in er.async_entries_for_config_entry(
                    entity_registry, self.config_entry.entry_id
                )
                if entity_entry.device_id == device_entry.id
            )
        }

        if not self.configurable_devices:
            return self.async_abort(reason="no_configurable_devices")

        return await self.async_step_device_selection(user_input=None)

    async def async_step_device_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select what devices to configure."""
        errors = {}
        if user_input is not None:
            if user_input.get(_INPUT_ENTRY_CLEAR_DEVICE_OPTIONS):
                # Reset all options
                return self.async_create_entry(data={})

            selected_devices: list[str] = (
                user_input.get(_INPUT_ENTRY_DEVICE_SELECTION) or []
            )
            if selected_devices:
                self.devices_to_configure = {
                    friendly_name: self.configurable_devices[friendly_name]
                    for friendly_name in selected_devices
                }

                return await self.async_step_configure_device(user_input=None)
            errors["base"] = "device_not_selected"

        return self.async_show_form(
            step_id="device_selection",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        _INPUT_ENTRY_CLEAR_DEVICE_OPTIONS,
                        default=False,
                    ): bool,
                    vol.Optional(
                        _INPUT_ENTRY_DEVICE_SELECTION,
                        default=self._get_current_configured_devices(),
                        description="Multiselect with list of devices to choose from",
                    ): cv.multi_select(dict.fromkeys(self.configurable_devices, False)),
                }
            ),
            errors=errors,
        )

    async def async_step_configure_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Config device options."""
        if user_input is not None:
            self._update_device_options(user_input)
            if self.devices_to_configure:
                return await self.async_step_configure_device(user_input=None)
            return self.async_create_entry(data=self.options)

        self.current_device, tuya_device_id = self.devices_to_configure.popitem()
        data_schema = vol.Schema(
            {
                vol.Required(
                    OPTION_ENTRY_COVER_POSITION_REVERSED,
                    default=self._get_current_setting(
                        tuya_device_id,
                        OPTION_ENTRY_COVER_POSITION_REVERSED,
                        False,
                    ),
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="configure_device",
            data_schema=data_schema,
            description_placeholders={"device_id": self.current_device},
        )

    @staticmethod
    def _get_device_product_id(entry: dr.DeviceEntry) -> str:
        return next(
            identifier[1] for identifier in entry.identifiers if identifier[0] == DOMAIN
        )

    @staticmethod
    def _get_device_friendly_name(entry: dr.DeviceEntry) -> str:
        if entry.name_by_user:
            return f"{entry.name_by_user} ({entry.name})"
        return entry.name or ""

    def _get_current_configured_devices(self) -> list[str]:
        """Get current list of devices that are configured."""
        configured_devices = self.options.get(OPTION_ENTRY_DEVICE_OPTIONS)
        if not configured_devices:
            return []
        return [
            friendly_name
            for friendly_name, tuya_device_id in self.configurable_devices.items()
            if tuya_device_id in configured_devices
        ]

    def _get_current_setting(self, device_id: str, setting: str, default: Any) -> Any:
        """Get current value for setting."""
        if entry_device_options := self.options.get(OPTION_ENTRY_DEVICE_OPTIONS):
            if device_options := entry_device_options.get(device_id):
                return device_options.get(setting)
        return default

    def _update_device_options(self, user_input: dict[str, Any]) -> None:
        """Update the global config with the new options for the current device."""
        options: dict[str, dict[str, Any]] = self.options.setdefault(
            OPTION_ENTRY_DEVICE_OPTIONS, {}
        )

        tuya_device_id = self.configurable_devices[self.current_device]
        device_options: dict[str, Any] = options.setdefault(tuya_device_id, {})
        device_options[OPTION_ENTRY_COVER_POSITION_REVERSED] = user_input[
            OPTION_ENTRY_COVER_POSITION_REVERSED
        ]

        self.options.update({OPTION_ENTRY_DEVICE_OPTIONS: options})
