"""Config flow for Ituran integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pyituran import Ituran
from pyituran.exceptions import IturanApiError, IturanAuthError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult

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
        vol.Required(CONF_ID_OR_PASSPORT): str,
        vol.Required(CONF_PHONE_NUMBER): str,
    }
)

STEP_OTP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OTP): str,
    }
)


class IturanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ituran."""

    _user_info: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ID_OR_PASSPORT])
            if self.source != SOURCE_REAUTH:
                self._abort_if_unique_id_configured()

            ituran = Ituran(
                user_input[CONF_ID_OR_PASSPORT],
                user_input[CONF_PHONE_NUMBER],
            )
            user_input[CONF_MOBILE_ID] = ituran.mobile_id
            try:
                authenticated = await ituran.is_authenticated()
                if not authenticated:
                    await ituran.request_otp()
            except IturanApiError:
                errors["base"] = "cannot_connect"
            except IturanAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if authenticated:
                    return self.async_create_entry(
                        title=f"Ituran {user_input[CONF_ID_OR_PASSPORT]}",
                        data=user_input,
                    )
                self._user_info = user_input
                return await self.async_step_otp()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the OTP step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            ituran = Ituran(
                self._user_info[CONF_ID_OR_PASSPORT],
                self._user_info[CONF_PHONE_NUMBER],
                self._user_info[CONF_MOBILE_ID],
            )
            try:
                await ituran.authenticate(user_input[CONF_OTP])
            except IturanApiError:
                errors["base"] = "cannot_connect"
            except IturanAuthError:
                errors["base"] = "invalid_otp"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data=self._user_info
                    )
                return self.async_create_entry(
                    title=f"Ituran {self._user_info[CONF_ID_OR_PASSPORT]}",
                    data=self._user_info,
                )

        return self.async_show_form(
            step_id="otp", data_schema=STEP_OTP_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._user_info = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation message."""
        if user_input is not None:
            return await self.async_step_user(self._user_info)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "phone_number": self._user_info[CONF_PHONE_NUMBER]
            },
        )
