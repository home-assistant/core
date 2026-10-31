"""Config flow for Xthings Cloud."""

from collections.abc import Mapping
from typing import Any, override

from ha_xthings_cloud import (
    XthingsCloudApiClient,
    XthingsCloudApiError,
    XthingsCloudAuthError,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.instance_id import async_get as async_get_instance_id

from .const import CONF_REFRESH_TOKEN, DOMAIN, LOGGER

ERROR_CODE_MAP: dict[int, str] = {
    20001: "token_invalid",
    21001: "email_empty",
    21002: "email_invalid",
    21004: "email_not_found",
    21011: "password_empty",
    21014: "password_wrong",
    21021: "user_disabled",
    21022: "user_not_logged_in",
    21023: "user_not_activated",
    20011: "token_invalid",
    20012: "token_expired",
    22001: "device_not_found",
    22003: "device_offline",
}


def _error_from_exception(err: XthingsCloudApiError) -> str:
    """Return translation key from error code."""
    return ERROR_CODE_MAP.get(err.code, "unknown")


class XthingsCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Xthings Cloud config flow."""

    VERSION = 1

    async def _async_login(
        self, email: str, password: str
    ) -> tuple[dict[str, Any] | None, dict[str, str]]:
        """Log in to Xthings Cloud and return token data or errors."""
        errors: dict[str, str] = {}
        instance_id = await async_get_instance_id(self.hass)
        session = async_get_clientsession(self.hass)
        client = XthingsCloudApiClient(session)
        try:
            token_data = await client.async_login(
                email, password, client_id=instance_id
            )
        except XthingsCloudAuthError as err:
            errors["base"] = _error_from_exception(err)
        except XthingsCloudApiError as err:
            errors["base"] = (
                _error_from_exception(err) if err.code else "cannot_connect"
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error during login")
            errors["base"] = "unknown"
        else:
            return token_data, errors
        return None, errors

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user input step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token_data, errors = await self._async_login(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if token_data is not None:
                await self.async_set_unique_id(token_data["user_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_TOKEN: token_data["token"],
                        CONF_REFRESH_TOKEN: token_data["refresh_token"],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_EMAIL): str,
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication by asking for the password."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        email = reauth_entry.data[CONF_EMAIL]

        if user_input is not None:
            token_data, errors = await self._async_login(
                email, user_input[CONF_PASSWORD]
            )
            if token_data is not None:
                await self.async_set_unique_id(token_data["user_id"])
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_TOKEN: token_data["token"],
                        CONF_REFRESH_TOKEN: token_data["refresh_token"],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_PASSWORD)): str}
            ),
            description_placeholders={"email": email},
            errors=errors,
        )
