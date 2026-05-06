"""Config flow to configure zone component."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.util.ssl import SSL_ALPN_HTTP11_HTTP2

from .const import DOMAIN

CREDENTIALS_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class AqualinkFlowHandler(ConfigFlow, domain=DOMAIN):
    """Aqualink config flow."""

    VERSION = 1

    async def _async_test_credentials(
        self, user_input: dict[str, Any]
    ) -> dict[str, str]:
        """Validate credentials against iAquaLink."""
        try:
            async with AqualinkClient(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                httpx_client=get_async_client(
                    self.hass, alpn_protocols=SSL_ALPN_HTTP11_HTTP2
                ),
            ):
                pass
        except AqualinkServiceUnauthorizedException:
            return {"base": "invalid_auth"}
        except AqualinkServiceException, httpx.HTTPError:
            return {"base": "cannot_connect"}

        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            errors = await self._async_test_credentials(user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=CREDENTIALS_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle flow triggered by an authentication failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle confirmation of reauthentication."""
        errors = {}

        config_entry = (
            self._get_reconfigure_entry()
            if self.source == SOURCE_RECONFIGURE
            else self._get_reauth_entry()
        )
        if user_input is not None:
            errors = await self._async_test_credentials(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    config_entry,
                    title=user_input[CONF_USERNAME],
                    data_updates={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id=(
                "reconfigure" if self.source == SOURCE_RECONFIGURE else "reauth_confirm"
            ),
            data_schema=CREDENTIALS_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        return await self.async_step_reauth_confirm(user_input)
