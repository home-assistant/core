"""Config flow for Xthings Cloud."""

from __future__ import annotations

from typing import Any

from ha_xthings_cloud import (
    XthingsCloudApiClient,
    XthingsCloudApiError,
    XthingsCloudAuthError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.instance_id import async_get as async_get_instance_id

from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN,
    DOMAIN,
    LOGGER,
)

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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user input step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                instance_id = await async_get_instance_id(self.hass)
                session = async_get_clientsession(self.hass)
                client = XthingsCloudApiClient(session)
                token_data = await client.async_login(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    client_id=instance_id,
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
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
