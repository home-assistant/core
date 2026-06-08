"""Config flow for Karakeep."""

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from aiokarakeep import (
    KarakeepApiError,
    KarakeepAuthError,
    KarakeepClient,
    KarakeepConnectionError,
    KarakeepInvalidResponseError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): str})
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
    }
)


class KarakeepConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Karakeep."""

    VERSION = 1

    async def _async_validate_input(self, url: str, token: str) -> dict[str, str]:
        """Validate the user input allows us to connect."""
        errors: dict[str, str] = {}

        session = async_get_clientsession(self.hass)
        client = KarakeepClient(url, token, session)

        try:
            await client.async_get_stats()
        except KarakeepAuthError:
            errors["base"] = "invalid_auth"
        except KarakeepConnectionError:
            errors["base"] = "cannot_connect"
        except KarakeepApiError, KarakeepInvalidResponseError:
            errors["base"] = "api_error"

        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = _normalize_url(user_input[CONF_URL])
            token = user_input[CONF_TOKEN].strip()

            if not _is_valid_url(url):
                errors["base"] = "invalid_url_format"
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()

                errors = await self._async_validate_input(url, token)
                if not errors:
                    return self.async_create_entry(
                        title="Karakeep",
                        data={
                            CONF_URL: url,
                            CONF_TOKEN: token,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new API token."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            errors = await self._async_validate_input(
                reauth_entry.data[CONF_URL], token
            )

            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={**reauth_entry.data, CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )


def _normalize_url(url: str) -> str:
    """Normalize a Karakeep URL."""
    return url.strip().rstrip("/")


def _is_valid_url(url: str) -> bool:
    """Return whether the URL looks valid."""
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
