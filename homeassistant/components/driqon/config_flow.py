"""Config and reauthentication flows for DRIQON."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    DriqonApi,
    DriqonApiError,
    DriqonAuthError,
    DriqonInvalidApiKeyError,
    DriqonRateLimitError,
)
from .const import DEFAULT_API_URL, FIREBASE_API_KEY, DOMAIN
from . import DriqonConfigEntry
from .types import DriqonConfigEntryData


class DriqonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle initial setup, reauthentication, and reconfiguration."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: DriqonConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Set up an account after validating DRIQON credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            result = await self._validate_credentials(user_input)
            if isinstance(result, str):
                errors["base"] = result
            else:
                auth = result
                await self.async_set_unique_id(auth["localId"])
                self._abort_if_unique_id_configured()
                data: DriqonConfigEntryData = {
                    CONF_EMAIL: user_input[CONF_EMAIL].strip(),
                    "refresh_token": auth["refreshToken"],
                    "uid": auth["localId"],
                }
                return self.async_create_entry(title=data[CONF_EMAIL], data=data)
        return self.async_show_form(
            step_id="user", data_schema=_user_schema(), errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, object]
    ) -> config_entries.ConfigFlowResult:
        """Start reauthentication after Firebase rejects the refresh token."""
        self._reauth_entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Reauthenticate the stored account and update its refresh token."""
        entry = self._reauth_entry
        if entry is None:
            return self.async_abort(reason="reauth_unsuccessful")
        errors: dict[str, str] = {}
        if user_input is not None:
            data = entry.data
            api = DriqonApi(
                async_get_clientsession(self.hass),
                data[CONF_EMAIL],
                api_key=FIREBASE_API_KEY,
                api_url=DEFAULT_API_URL,
            )
            try:
                auth = await api.sign_in(user_input[CONF_PASSWORD])
                if auth["localId"] != data["uid"]:
                    errors["base"] = "account_mismatch"
                else:
                    await api.devices()
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={
                            "refresh_token": auth["refreshToken"],
                        },
                    )
            except DriqonInvalidApiKeyError:
                errors["base"] = "invalid_api_key"
            except DriqonAuthError:
                errors["base"] = "invalid_auth"
            except DriqonRateLimitError:
                errors["base"] = "rate_limited"
            except DriqonApiError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Reconnect the DRIQON account without exposing service settings."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            result = await self._validate_credentials(user_input)
            if isinstance(result, str):
                errors["base"] = result
            else:
                auth = result
                if auth["localId"] != entry.data["uid"]:
                    errors["base"] = "account_mismatch"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        reason="reconfigure_successful",
                        data_updates={
                            CONF_EMAIL: user_input[CONF_EMAIL].strip(),
                            "refresh_token": auth["refreshToken"],
                        },
                    )
        current = entry.data
        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=current[CONF_EMAIL]): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    async def _validate_credentials(
        self, user_input: dict[str, str]
    ) -> dict[str, str] | str:
        """Validate credentials against the fixed Firebase and DRIQON services."""
        api = DriqonApi(
            async_get_clientsession(self.hass),
            user_input[CONF_EMAIL].strip(),
            api_key=FIREBASE_API_KEY,
            api_url=DEFAULT_API_URL,
        )
        try:
            auth = await api.sign_in(user_input[CONF_PASSWORD])
            await api.devices()
        except DriqonInvalidApiKeyError:
            return "invalid_api_key"
        except DriqonAuthError:
            return "invalid_auth"
        except DriqonRateLimitError:
            return "rate_limited"
        except DriqonApiError:
            return "cannot_connect"
        return auth


def _user_schema(*, email: str = "") -> vol.Schema:
    """Build the initial account sign-in form."""
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL, default=email): str,
            vol.Required(CONF_PASSWORD): str,
        }
    )
