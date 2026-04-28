"""Config flow to configure zone component."""

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


def _username_unique_id(username: str) -> str:
    """Normalize a username for config entry deduplication."""
    return username.casefold()


class AqualinkFlowHandler(ConfigFlow, domain=DOMAIN):
    """Aqualink config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    async def _async_validate_credentials(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], str | None]:
        """Validate credentials and return the stable account ID."""
        try:
            async with AqualinkClient(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                httpx_client=get_async_client(
                    self.hass, alpn_protocols=SSL_ALPN_HTTP11_HTTP2
                ),
            ) as client:
                return {}, client.user_id
        except AqualinkServiceUnauthorizedException:
            return {"base": "invalid_auth"}, None
        except AqualinkServiceException, httpx.HTTPError:
            return {"base": "cannot_connect"}, None

    def _find_existing_entry_by_username(self, username: str) -> str | None:
        """Find an existing entry using the legacy username-based identity."""
        normalized_username = _username_unique_id(username)
        for entry in self._async_current_entries():
            if _username_unique_id(entry.data[CONF_USERNAME]) == normalized_username:
                return entry.entry_id

        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, account_id = await self._async_validate_credentials(user_input)
            if not errors and account_id is not None:
                if self._find_existing_entry_by_username(user_input[CONF_USERNAME]):
                    return self.async_abort(reason="already_configured")

                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_configured()
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
        errors: dict[str, str] = {}

        config_entry = (
            self._get_reconfigure_entry()
            if self.source == SOURCE_RECONFIGURE
            else self._get_reauth_entry()
        )
        if user_input is not None:
            errors, account_id = await self._async_validate_credentials(user_input)
            if not errors and account_id is not None:
                legacy_unique_id = _username_unique_id(reauth_entry.data[CONF_USERNAME])
                if reauth_entry.unique_id in (None, legacy_unique_id):
                    if (
                        _username_unique_id(user_input[CONF_USERNAME])
                        != legacy_unique_id
                    ):
                        return self.async_abort(reason="account_mismatch")
                else:
                    await self.async_set_unique_id(account_id)
                    self._abort_if_unique_id_mismatch(reason="account_mismatch")

                existing_entry = (
                    self.hass.config_entries.async_entry_for_domain_unique_id(
                        DOMAIN, account_id
                    )
                )
                if existing_entry and existing_entry.entry_id != reauth_entry.entry_id:
                    return self.async_abort(reason="already_configured")

                self.hass.config_entries.async_update_entry(
                    reauth_entry, unique_id=account_id
                )
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
