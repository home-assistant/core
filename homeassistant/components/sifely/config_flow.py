"""Config flow for the Sifely smart lock integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from pysifely import DEFAULT_BASE_URL, SifelyApiClient, SifelyApiError, SifelyAuthError
from .const import (
    CONF_BASE_URL,
    CONF_REFRESH_TOKEN,
    DEFAULT_CLIENT_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class SifelyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sifely."""

    VERSION = 1

    async def _async_validate(self, email: str, password: str) -> dict[str, str]:
        """Validate credentials against the Sifely API and return tokens."""
        session = async_get_clientsession(self.hass)
        password_md5 = SifelyApiClient.md5_password(password)
        return await SifelyApiClient.login(
            base_url=DEFAULT_BASE_URL,
            username=email,
            password_md5=password_md5,
            client_id=DEFAULT_CLIENT_ID,
            session=session,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()

            try:
                result = await self._async_validate(
                    email, user_input[CONF_PASSWORD]
                )
            except SifelyAuthError:
                errors["base"] = "invalid_auth"
            except SifelyApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Sifely login")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Sifely ({email})",
                    data={
                        CONF_EMAIL: email,
                        CONF_BASE_URL: DEFAULT_BASE_URL,
                        CONF_CLIENT_ID: DEFAULT_CLIENT_ID,
                        CONF_ACCESS_TOKEN: result["access_token"],
                        CONF_REFRESH_TOKEN: result.get("refresh_token", ""),
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when the token becomes invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication by asking for the password again."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        email = reauth_entry.data[CONF_EMAIL]

        if user_input is not None:
            try:
                result = await self._async_validate(
                    email, user_input[CONF_PASSWORD]
                )
            except SifelyAuthError:
                errors["base"] = "invalid_auth"
            except SifelyApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Sifely re-auth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_ACCESS_TOKEN: result["access_token"],
                        CONF_REFRESH_TOKEN: result.get("refresh_token", ""),
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_DATA_SCHEMA,
            description_placeholders={"email": email},
            errors=errors,
        )
