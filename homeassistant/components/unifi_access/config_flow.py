"""Config flow for UniFi Access integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from unifi_access_api import ApiAuthError, ApiConnectionError, UnifiAccessApiClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.ssl import create_no_verify_ssl_context

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class UnifiAccessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UniFi Access."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate user input and return errors dict."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(
            self.hass, verify_ssl=user_input[CONF_VERIFY_SSL]
        )
        ssl_context = (
            None if user_input[CONF_VERIFY_SSL] else create_no_verify_ssl_context()
        )
        client = UnifiAccessApiClient(
            host=user_input[CONF_HOST],
            api_token=user_input[CONF_API_TOKEN],
            session=session,
            verify_ssl=user_input[CONF_VERIFY_SSL],
            ssl_context=ssl_context,
        )
        try:
            await client.authenticate()
        except ApiAuthError:
            errors["base"] = "invalid_auth"
        except ApiConnectionError:
            errors["base"] = "cannot_connect"
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
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            errors = await self._validate_input(user_input)
            if not errors:
                return self.async_create_entry(
                    title="UniFi Access",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_API_TOKEN): str,
                    vol.Required(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST]},
            )
            errors = await self._validate_input(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=user_input,
                )

        suggested_values = user_input or dict(reconfigure_entry.data)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_API_TOKEN): str,
                        vol.Required(CONF_VERIFY_SSL): bool,
                    }
                ),
                suggested_values,
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirm."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            errors = await self._validate_input(
                {
                    **reauth_entry.data,
                    CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                }
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            description_placeholders={CONF_HOST: reauth_entry.data[CONF_HOST]},
            errors=errors,
        )
