"""Config flow for Tuya."""
from __future__ import annotations

from io import BytesIO
from typing import Any

import segno
from tuya_sharing import LoginControl
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

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


class TuyaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Tuya config flow."""

    __user_code: str
    __qr_code: str
    __qr_image: str

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
            response = await self.hass.async_add_executor_job(
                self.__login_control.qr_code,
                TUYA_CLIENT_ID,
                TUYA_SCHEMA,
                user_input[CONF_USER_CODE],
            )
            if response.get(TUYA_RESPONSE_SUCCESS, False):
                self.__user_code = user_input[CONF_USER_CODE]
                self.__qr_code = response[TUYA_RESPONSE_RESULT][TUYA_RESPONSE_QR_CODE]
                self.__qr_image = _generate_qr_code(self.__qr_code)
                return self.async_show_form(
                    step_id="scan",
                    description_placeholders={TUYA_RESPONSE_QR_CODE: self.__qr_image},
                )

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
        if user_input is not None:
            ret, info = await self.hass.async_add_executor_job(
                self.__login_control.login_result,
                self.__qr_code,
                TUYA_CLIENT_ID,
                self.__user_code,
            )
            if ret:
                return self.async_create_entry(
                    title=info.get("username"),
                    data={
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
                    },
                )

        return self.async_show_form(
            step_id="scan",
            errors={"base": "login_error"},
            description_placeholders={
                TUYA_RESPONSE_QR_CODE: self.__qr_image,
                TUYA_RESPONSE_MSG: info.get(TUYA_RESPONSE_MSG),
                TUYA_RESPONSE_CODE: info.get(TUYA_RESPONSE_CODE),
            },
        )


def _generate_qr_code(data: str) -> str:
    """Create an SVG QR code that can be scanned with the Smart Life app."""
    qr_code = segno.make(f"tuyaSmart--qrLogin?token={data}", error="h")
    with BytesIO() as buffer:
        qr_code.save(
            buffer,
            kind="svg",
            border=5,
            scale=5,
            xmldecl=False,
            svgns=False,
            svgclass=None,
            lineclass=None,
            svgversion=2,
            dark="#1abcf2",
        )
        return str(buffer.getvalue().decode("ascii"))
