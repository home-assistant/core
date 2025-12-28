"""Config flow for the Fressnapf Tracker integration."""

from collections.abc import Mapping
import logging
from typing import Any

from fressnapftracker import (
    AuthClient,
    FressnapfTrackerInvalidPhoneNumberError,
    FressnapfTrackerInvalidTokenError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_PHONE_NUMBER, CONF_SMS_CODE, CONF_USER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PHONE_NUMBER): str,
    }
)
STEP_SMS_CODE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SMS_CODE): int,
    }
)


class FressnapfTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fressnapf Tracker."""

    VERSION = 1

    def __init__(self) -> None:
        """Init Config Flow."""
        self._context: dict[str, Any] = {}
        self._auth_client: AuthClient | None = None

    @property
    def auth_client(self) -> AuthClient:
        """Return the auth client, creating it if needed."""
        if self._auth_client is None:
            self._auth_client = AuthClient(client=get_async_client(self.hass))
        return self._auth_client

    async def _async_request_sms_code(
        self, phone_number: str
    ) -> tuple[dict[str, str], bool]:
        """Request SMS code and return errors dict and success flag."""
        errors: dict[str, str] = {}
        try:
            response = await self.auth_client.request_sms_code(
                phone_number=phone_number
            )
        except FressnapfTrackerInvalidPhoneNumberError:
            errors["base"] = "invalid_phone_number"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug("SMS code request response: %s", response)
            self._context[CONF_USER_ID] = response.id
            self._context[CONF_PHONE_NUMBER] = phone_number
            return errors, True
        return errors, False

    async def _async_verify_sms_code(
        self, sms_code: int
    ) -> tuple[dict[str, str], str | None]:
        """Verify SMS code and return errors and access_token."""
        errors: dict[str, str] = {}
        try:
            verification_response = await self.auth_client.verify_phone_number(
                user_id=self._context[CONF_USER_ID],
                sms_code=sms_code,
            )
        except FressnapfTrackerInvalidTokenError:
            errors["base"] = "invalid_sms_code"
        except Exception:
            _LOGGER.exception("Unexpected exception during SMS code verification")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug(
                "Phone number verification response: %s", verification_response
            )
            return errors, verification_response.user_token.access_token
        return errors, None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_PHONE_NUMBER: user_input[CONF_PHONE_NUMBER]}
            )
            errors, success = await self._async_request_sms_code(
                user_input[CONF_PHONE_NUMBER]
            )
            if success:
                await self.async_set_unique_id(str(self._context[CONF_USER_ID]))
                self._abort_if_unique_id_configured()
                return await self.async_step_sms_code()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_sms_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the SMS code step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, access_token = await self._async_verify_sms_code(
                user_input[CONF_SMS_CODE]
            )
            if access_token:
                return self.async_create_entry(
                    title=self._context[CONF_PHONE_NUMBER],
                    data={
                        CONF_PHONE_NUMBER: self._context[CONF_PHONE_NUMBER],
                        CONF_USER_ID: self._context[CONF_USER_ID],
                        CONF_ACCESS_TOKEN: access_token,
                    },
                )

        return self.async_show_form(
            step_id="sms_code",
            data_schema=STEP_SMS_CODE_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_reauth_reconfigure(
        self,
        user_input: dict[str, Any] | None,
        entry: Any,
        step_id: str,
    ) -> ConfigFlowResult:
        """Request a new sms code for reauth or reconfigure flows."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, success = await self._async_request_sms_code(
                user_input[CONF_PHONE_NUMBER]
            )
            if success:
                if entry.data[CONF_USER_ID] != self._context[CONF_USER_ID]:
                    errors["base"] = "account_change_not_allowed"
                elif self.source == SOURCE_REAUTH:
                    return await self.async_step_reauth_sms_code()
                elif self.source == SOURCE_RECONFIGURE:
                    return await self.async_step_reconfigure_sms_code()

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                {CONF_PHONE_NUMBER: entry.data.get(CONF_PHONE_NUMBER)},
            ),
            errors=errors,
        )

    async def _async_reauth_reconfigure_sms_code(
        self,
        user_input: dict[str, Any] | None,
        entry: Any,
        step_id: str,
    ) -> ConfigFlowResult:
        """Verify SMS code for reauth or reconfigure flows."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, access_token = await self._async_verify_sms_code(
                user_input[CONF_SMS_CODE]
            )
            if access_token:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_PHONE_NUMBER: self._context[CONF_PHONE_NUMBER],
                        CONF_ACCESS_TOKEN: access_token,
                    },
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=STEP_SMS_CODE_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation step."""
        return await self._async_reauth_reconfigure(
            user_input,
            self._get_reauth_entry(),
            "reauth_confirm",
        )

    async def async_step_reauth_sms_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the SMS code step during reauth."""
        return await self._async_reauth_reconfigure_sms_code(
            user_input,
            self._get_reauth_entry(),
            "reauth_sms_code",
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        return await self._async_reauth_reconfigure(
            user_input,
            self._get_reconfigure_entry(),
            "reconfigure",
        )

    async def async_step_reconfigure_sms_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the SMS code step during reconfiguration."""
        return await self._async_reauth_reconfigure_sms_code(
            user_input,
            self._get_reconfigure_entry(),
            "reconfigure_sms_code",
        )
