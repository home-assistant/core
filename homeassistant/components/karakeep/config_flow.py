"""Config flow for Karakeep."""

from collections.abc import Mapping
import logging
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
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_VERIFY_SSL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): str})
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


class KarakeepConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Karakeep."""

    VERSION = 1

    async def _async_validate_input(
        self, url: str, token: str, verify_ssl: bool
    ) -> dict[str, str]:
        """Validate the user input allows us to connect."""
        errors: dict[str, str] = {}

        session = async_get_clientsession(self.hass, verify_ssl)
        client = KarakeepClient(url, token, session)

        try:
            await client.async_get_stats()
        except KarakeepAuthError:
            errors["base"] = "invalid_auth"
        except KarakeepConnectionError:
            errors["base"] = "cannot_connect"
        except (KarakeepApiError, KarakeepInvalidResponseError):
            errors["base"] = "api_error"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = _normalize_url(user_input[CONF_URL])
            token = user_input[CONF_TOKEN].strip()
            verify_ssl = user_input[CONF_VERIFY_SSL]

            if not _is_valid_url(url):
                errors["base"] = "invalid_url_format"
            else:
                self._async_abort_entries_match({CONF_URL: url})

                errors = await self._async_validate_input(url, token, verify_ssl)
                if not errors:
                    return self.async_create_entry(
                        title="Karakeep",
                        data={
                            CONF_URL: url,
                            CONF_TOKEN: token,
                            CONF_VERIFY_SSL: verify_ssl,
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
                reauth_entry.data[CONF_URL],
                token,
                reauth_entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
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
