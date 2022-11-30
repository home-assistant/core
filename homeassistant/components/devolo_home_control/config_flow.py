"""Config flow to configure the devolo home control integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from . import configure_mydevolo
from .const import CONF_MYDEVOLO, DEFAULT_MYDEVOLO, DOMAIN, SUPPORTED_MODEL_TYPES
from .exceptions import CredentialsInvalid, UuidChanged


class DevoloHomeControlFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a devolo HomeControl config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize devolo Home Control flow."""
        self.data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }
        self._reauth_entry: ConfigEntry | None = None
        self._url = DEFAULT_MYDEVOLO

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if self.show_advanced_options:
            self.data_schema[vol.Required(CONF_MYDEVOLO, default=self._url)] = str
        if user_input is None:
            return self._show_form(step_id="user")
        try:
            return await self._connect_mydevolo(user_input)
        except CredentialsInvalid:
            return self._show_form(step_id="user", errors={"base": "invalid_auth"})

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        # Check if it is a gateway
        if discovery_info.properties.get("MT") in SUPPORTED_MODEL_TYPES:
            await self._async_handle_discovery_without_unique_id()
            return await self.async_step_zeroconf_confirm()
        return self.async_abort(reason="Not a devolo Home Control gateway.")

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by zeroconf."""
        if user_input is None:
            return self._show_form(step_id="zeroconf_confirm")
        try:
            return await self._connect_mydevolo(user_input)
        except CredentialsInvalid:
            return self._show_form(
                step_id="zeroconf_confirm", errors={"base": "invalid_auth"}
            )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauthentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._url = entry_data[CONF_MYDEVOLO]
        self.data_schema = {
            vol.Required(CONF_USERNAME, default=entry_data[CONF_USERNAME]): str,
            vol.Required(CONF_PASSWORD): str,
        }
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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

    async def _connect_mydevolo(self, user_input: dict[str, Any]) -> FlowResult:
        """Connect to mydevolo."""
        user_input[CONF_MYDEVOLO] = user_input.get(CONF_MYDEVOLO, self._url)
        mydevolo = configure_mydevolo(conf=user_input)
        credentials_valid = await self.hass.async_add_executor_job(
            mydevolo.credentials_valid
        )
        if not credentials_valid:
            raise CredentialsInvalid
        uuid = await self.hass.async_add_executor_job(mydevolo.uuid)

        if not self._reauth_entry:
            await self.async_set_unique_id(uuid)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="devolo Home Control",
                data={
                    CONF_PASSWORD: mydevolo.password,
                    CONF_USERNAME: mydevolo.user,
                    CONF_MYDEVOLO: mydevolo.url,
                },
            )

        if self._reauth_entry.unique_id != uuid:
            # The old user and the new user are not the same. This could mess-up everything as all unique IDs might change.
            raise UuidChanged

        self.hass.config_entries.async_update_entry(
            self._reauth_entry, data=user_input, unique_id=uuid
        )
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
        )
        return self.async_abort(reason="reauth_successful")

    @callback
    def _show_form(
        self, step_id: str, errors: dict[str, str] | None = None
    ) -> FlowResult:
        """Show the form to the user."""
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )
