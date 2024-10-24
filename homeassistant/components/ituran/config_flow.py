"""Config flow for Ituran integration."""

from __future__ import annotations

import logging
from typing import Any

from pyituran import Ituran
from pyituran.exceptions import IturanApiError, IturanAuthError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_ID_OR_PASSPORT,
    CONF_MOBILE_ID,
    CONF_OTP,
    CONF_PHONE_NUMBER,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID_OR_PASSPORT, description="ID or passport number"): str,
        vol.Required(CONF_PHONE_NUMBER, description="Mobile phone number"): str,
        vol.Optional(
            CONF_MOBILE_ID, description="Mobile ID (leave empty if unknown)"
        ): str,
    }
)

STEP_OTP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OTP, description="OTP"): str,
    }
)


async def validate_credentials(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Validate the user credentials and request OTP, if needed."""

    ituran = Ituran(
        data[CONF_ID_OR_PASSPORT], data[CONF_PHONE_NUMBER], data.get(CONF_MOBILE_ID)
    )
    data[CONF_MOBILE_ID] = ituran.mobile_id

    try:
        if await ituran.is_authenticated():
            return data, True
    except IturanApiError as err:
        raise CannotConnect from err

    try:
        await ituran.request_otp()
    except IturanAuthError as err:
        raise InvalidAuth from err

    return data, False


async def validate_otp(
    hass: HomeAssistant, user_info: dict[str, Any], data: dict[str, Any]
) -> None:
    """Validate the OTP."""

    ituran = Ituran(
        user_info[CONF_ID_OR_PASSPORT],
        user_info[CONF_PHONE_NUMBER],
        user_info[CONF_MOBILE_ID],
    )

    try:
        await ituran.authenticate(data[CONF_OTP])
    except IturanApiError as err:
        raise CannotConnect from err
    except IturanAuthError as err:
        raise InvalidOtp from err


class IturanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ituran."""

    VERSION = 1

    _user_info: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the inial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if self.unique_id is None:
                await self.async_set_unique_id(user_input[CONF_ID_OR_PASSPORT])
                self._abort_if_unique_id_configured()

            try:
                info, authenticated = await validate_credentials(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if authenticated:
                    return self.async_create_entry(
                        title=f"Ituran {info[CONF_ID_OR_PASSPORT]}", data=info
                    )
                self._user_info = info
                return await self.async_step_otp()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the inial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_otp(self.hass, self._user_info, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidOtp:
                errors["base"] = "invalid_otp"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Ituran {self._user_info[CONF_ID_OR_PASSPORT]}",
                    data=self._user_info,
                )

        return self.async_show_form(
            step_id="otp", data_schema=STEP_OTP_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidOtp(HomeAssistantError):
    """Error to indicate OTP is wrong."""
