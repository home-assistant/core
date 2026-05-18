"""Config flow for Karakeep."""

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
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class KarakeepConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Karakeep."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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
                else:
                    return self.async_create_entry(
                        title="Karakeep",
                        data={
                            CONF_URL: url,
                            CONF_TOKEN: token,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )


def _normalize_url(url: str) -> str:
    """Normalize a Karakeep URL."""
    return url.strip().rstrip("/")


def _is_valid_url(url: str) -> bool:
    """Return whether the URL looks valid."""
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
