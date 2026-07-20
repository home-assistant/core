"""Config flow for Karakeep."""

import logging
from typing import Any, override

from aiokarakeep import (
    KarakeepApiError,
    KarakeepAuthError,
    KarakeepClient,
    KarakeepConnectionError,
    KarakeepInvalidResponseError,
)
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_VERIFY_SSL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


class KarakeepConfigFlow(ConfigFlow, domain=DOMAIN):
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
        except KarakeepApiError, KarakeepInvalidResponseError:
            errors["base"] = "api_error"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return errors

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = _normalize_url(user_input[CONF_URL])
            token = user_input[CONF_TOKEN].strip()
            verify_ssl = user_input[CONF_VERIFY_SSL]

            if url is None:
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


def _normalize_url(raw_url: str) -> str | None:
    """Return the normalized base URL, or None if it is not a valid URL."""
    try:
        parsed_url = URL(raw_url.strip())
    except ValueError:
        return None
    if parsed_url.scheme not in ("http", "https") or not parsed_url.host:
        return None
    return str(parsed_url).rstrip("/")
