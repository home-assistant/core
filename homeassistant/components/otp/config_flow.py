"""Config flow for One-Time Password (OTP) integration."""

from __future__ import annotations

import binascii
import logging
from re import sub
from typing import Any

import pyotp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CODE, CONF_NAME, CONF_TOKEN
from homeassistant.helpers.selector import (
    BooleanSelector,
    BooleanSelectorConfig,
    QrCodeSelector,
    QrCodeSelectorConfig,
    QrErrorCorrectionLevel,
)

from .const import CONF_NEW_TOKEN, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TOKEN): str,
        vol.Optional(CONF_NEW_TOKEN): BooleanSelector(BooleanSelectorConfig()),
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
    }
)

STEP_CONFIRM_DATA_SCHEMA = vol.Schema({vol.Required(CONF_CODE): str})


class TOTPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for One-Time Password (OTP)."""

    VERSION = 1
    user_input: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_TOKEN) and not user_input.get(CONF_NEW_TOKEN):
                user_input[CONF_TOKEN] = sub(r"\s+", "", user_input[CONF_TOKEN])
                try:
                    await self.hass.async_add_executor_job(
                        pyotp.TOTP(user_input[CONF_TOKEN]).now
                    )
                except binascii.Error:
                    errors["base"] = "invalid_token"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(user_input[CONF_TOKEN])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=user_input,
                    )
            elif user_input.get(CONF_NEW_TOKEN):
                user_input[CONF_TOKEN] = await self.hass.async_add_executor_job(
                    pyotp.random_base32
                )
                self.user_input = user_input
                return await self.async_step_confirm()
            else:
                errors["base"] = "invalid_token"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> ConfigFlowResult:
        """Import config from yaml."""

        await self.async_set_unique_id(import_info[CONF_TOKEN])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=import_info.get(CONF_NAME, DEFAULT_NAME),
            data=import_info,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the confirmation step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            if await self.hass.async_add_executor_job(
                pyotp.TOTP(self.user_input[CONF_TOKEN]).verify, user_input["code"]
            ):
                return self.async_create_entry(
                    title=self.user_input[CONF_NAME],
                    data={
                        CONF_NAME: self.user_input[CONF_NAME],
                        CONF_TOKEN: self.user_input[CONF_TOKEN],
                    },
                )

            errors["base"] = "invalid_code"

        provisioning_uri = await self.hass.async_add_executor_job(
            pyotp.TOTP(self.user_input[CONF_TOKEN]).provisioning_uri,
            self.user_input[CONF_NAME],
            "Home Assistant",
        )
        data_schema = STEP_CONFIRM_DATA_SCHEMA.extend(
            {
                vol.Optional("qr_code"): QrCodeSelector(
                    config=QrCodeSelectorConfig(
                        data=provisioning_uri,
                        scale=6,
                        error_correction_level=QrErrorCorrectionLevel.QUARTILE,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="confirm",
            data_schema=data_schema,
            description_placeholders={
                "auth_app1": "[Google Authenticator](https://support.google.com/accounts/answer/1066447)",
                "auth_app2": "[Authy](https://authy.com/)",
                "code": self.user_input[CONF_TOKEN],
            },
            errors=errors,
        )
