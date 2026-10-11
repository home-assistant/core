"""Config flow for Koito."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, override
from urllib.parse import urlsplit, urlunsplit

from aiokoito import (
    KoitoApi,
    KoitoAuthenticationError,
    KoitoConnectionError,
    KoitoResponseError,
)
import probatio

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

if TYPE_CHECKING:
    from aiohttp import ClientSession


class KoitoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Koito."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect connection details and validate them against Koito."""
        errors: dict[str, str] = {}
        if user_input is not None:
            raw_url = user_input[CONF_URL].strip()
            api_key = user_input[CONF_API_KEY].strip()
            normalized_url = _normalize_url(raw_url)

            if normalized_url is None:
                errors["base"] = "invalid_url"
            else:
                self._async_abort_entries_match({CONF_URL: normalized_url})
                error = await _async_validate_connection(
                    normalized_url, api_key, async_get_clientsession(self.hass)
                )
                if error:
                    errors["base"] = error
                else:
                    self._async_abort_entries_match({CONF_URL: normalized_url})
                    return self.async_create_entry(
                        title=urlsplit(normalized_url).netloc,
                        data={CONF_URL: normalized_url, CONF_API_KEY: api_key},
                    )

        schema = probatio.Schema(
            {
                probatio.Required(CONF_URL): str,
                probatio.Required(CONF_API_KEY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"url_example": "https://koito.example:8484"},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle an API key rejected during polling."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and save a replacement API key."""
        entry = self._get_reauth_entry()

        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            error = await _async_validate_connection(
                entry.data[CONF_URL], api_key, async_get_clientsession(self.hass)
            )
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: api_key}
                )

        schema = probatio.Schema(
            {
                probatio.Required(CONF_API_KEY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            description_placeholders={"url": entry.data[CONF_URL]},
            errors=errors,
        )


def _normalize_url(value: str) -> str | None:
    """Return a normalized HTTP(S) origin URL, or None for invalid input."""
    try:
        parsed = urlsplit(value.strip())
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            return None
        # Accessing .port validates malformed and out-of-range port values.
        port = parsed.port
    except ValueError:
        return None

    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    if (parsed.scheme.lower(), port) in {("http", 80), ("https", 443)}:
        port = None
    netloc = f"{host}:{port}" if port is not None else host
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path.rstrip("/"), "", ""))


async def _async_validate_connection(
    base_url: str, api_key: str, session: ClientSession
) -> str | None:
    """Validate credentials with the lightweight summary endpoint."""
    try:
        await KoitoApi(base_url, api_key, session).async_get_summary()
    except KoitoAuthenticationError:
        return "invalid_auth"
    except KoitoConnectionError, KoitoResponseError:
        return "cannot_connect"
    return None
