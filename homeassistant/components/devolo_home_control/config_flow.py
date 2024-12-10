"""Config flow to configure the devolo home control integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from . import configure_mydevolo
from .const import DOMAIN, SUPPORTED_MODEL_TYPES
from .exceptions import CredentialsInvalid, UuidChanged


class DevoloHomeControlFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a devolo HomeControl config flow."""

    VERSION = 1

    _reauth_entry: ConfigEntry

    def __init__(self) -> None:
        """Initialize devolo Home Control flow."""
        self.data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_form(step_id="user")
        try:
            return await self._connect_mydevolo(user_input)
        except CredentialsInvalid:
            return self._show_form(step_id="user", errors={"base": "invalid_auth"})

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        # Check if it is a gateway
        if discovery_info.properties.get("MT") in SUPPORTED_MODEL_TYPES:
            await self._async_handle_discovery_without_unique_id()
            return await self.async_step_zeroconf_confirm()
        return self.async_abort(reason="Not a devolo Home Control gateway.")

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        if user_input is None:
            return self._show_form(step_id="zeroconf_confirm")
        try:
            return await self._connect_mydevolo(user_input)
        except CredentialsInvalid:
            return self._show_form(
                step_id="zeroconf_confirm", errors={"base": "invalid_auth"}
            )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        self._reauth_entry = self._get_reauth_entry()
        self.data_schema = {
            vol.Required(CONF_USERNAME, default=entry_data[CONF_USERNAME]): str,
            vol.Required(CONF_PASSWORD): str,
        }
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by reauthentication."""
        if user_input is None:
            return self._show_form(step_id="reauth_confirm")
        try:
            return await self._connect_mydevolo(user_input)
        except CredentialsInvalid:
            return self._show_form(
                step_id="reauth_confirm", errors={"base": "invalid_auth"}
            )
        except UuidChanged:
            return self._show_form(
                step_id="reauth_confirm", errors={"base": "reauth_failed"}
            )

    async def _connect_mydevolo(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Connect to mydevolo."""
        mydevolo = configure_mydevolo(conf=user_input)
        credentials_valid = await self.hass.async_add_executor_job(
            mydevolo.credentials_valid
        )
        if not credentials_valid:
            raise CredentialsInvalid
        uuid = await self.hass.async_add_executor_job(mydevolo.uuid)

        if self.source != SOURCE_REAUTH:
            await self.async_set_unique_id(uuid)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="devolo Home Control",
                data={
                    CONF_PASSWORD: mydevolo.password,
                    CONF_USERNAME: mydevolo.user,
                },
            )

        if self._reauth_entry.unique_id != uuid:
            # The old user and the new user are not the same. This could mess-up everything as all unique IDs might change.
            raise UuidChanged

        return self.async_update_reload_and_abort(
            self._reauth_entry, data=user_input, unique_id=uuid
        )

    @callback
    def _show_form(
        self, step_id: str, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the form to the user."""
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )
