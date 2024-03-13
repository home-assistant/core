"""Config flow for Tuya."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tuya_sharing import LoginControl
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
    TUYA_CLIENT_ID,
    TUYA_RESPONSE_CODE,
    TUYA_RESPONSE_MSG,
    TUYA_RESPONSE_QR_CODE,
    TUYA_RESPONSE_RESULT,
    TUYA_RESPONSE_SUCCESS,
    TUYA_SCHEMA,
)


class TuyaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Tuya config flow."""

    __user_code: str
    __qr_code: str
    __reauth_entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.__login_control = LoginControl()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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
    ) -> FlowResult:
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

        if self.__reauth_entry:
            return self.async_update_reload_and_abort(
                self.__reauth_entry,
                data=entry_data,
            )

        return self.async_create_entry(
            title=info.get("username"),
            data=entry_data,
        )

    async def async_step_reauth(self, _: Mapping[str, Any]) -> FlowResult:
        """Handle initiation of re-authentication with Tuya."""
        self.__reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        if self.__reauth_entry and CONF_USER_CODE in self.__reauth_entry.data:
            success, _ = await self.__async_get_qr_code(
                self.__reauth_entry.data[CONF_USER_CODE]
            )
            if success:
                return await self.async_step_scan()

        return await self.async_step_reauth_user_code()

    async def async_step_reauth_user_code(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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
