"""Config flow for the Uptime Kuma integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pythonkuma import (
    UptimeKuma,
    UptimeKumaAuthenticationException,
    UptimeKumaException,
)
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.URL,
                autocomplete="url",
            ),
        ),
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
        vol.Optional(CONF_API_KEY, default=""): str,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Optional(CONF_API_KEY, default=""): str})


async def validate_connection(
    hass: HomeAssistant,
    url: URL | str,
    verify_ssl: bool,
    api_key: str,
) -> dict[str, str]:
    """Validate Uptime Kuma connectivity."""
    errors: dict[str, str] = {}
    session = async_get_clientsession(hass, verify_ssl)
    uptime_kuma = UptimeKuma(session, url, api_key)

    try:
        await uptime_kuma.metrics()
    except UptimeKumaAuthenticationException:
        errors["base"] = "invalid_auth"
    except UptimeKumaException:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    return errors


class UptimeKumaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Uptime Kuma."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = URL(user_input[CONF_URL])
            self._async_abort_entries_match({CONF_URL: url.human_repr()})

            if not (
                errors := await validate_connection(
                    self.hass,
                    url,
                    user_input[CONF_VERIFY_SSL],
                    user_input[CONF_API_KEY],
                )
            ):
                return self.async_create_entry(
                    title=url.host or "",
                    data={**user_input, CONF_URL: url.human_repr()},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}

        entry = self._get_reauth_entry()

        if user_input is not None:
            if not (
                errors := await validate_connection(
                    self.hass,
                    entry.data[CONF_URL],
                    entry.data[CONF_VERIFY_SSL],
                    user_input[CONF_API_KEY],
                )
            ):
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_REAUTH_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure flow."""
        errors: dict[str, str] = {}

        entry = self._get_reconfigure_entry()

        if user_input is not None:
            url = URL(user_input[CONF_URL])
            self._async_abort_entries_match({CONF_URL: url.human_repr()})

            if not (
                errors := await validate_connection(
                    self.hass,
                    url,
                    user_input[CONF_VERIFY_SSL],
                    user_input[CONF_API_KEY],
                )
            ):
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={**user_input, CONF_URL: url.human_repr()},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA,
                suggested_values=user_input or entry.data,
            ),
            errors=errors,
        )
