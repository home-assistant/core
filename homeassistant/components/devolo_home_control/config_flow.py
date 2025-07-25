"""Config flow to configure the devolo home control integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import configure_mydevolo
from .const import DOMAIN, SUPPORTED_MODEL_TYPES
from .exceptions import CredentialsInvalid, UuidChanged

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class DevoloHomeControlFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a devolo HomeControl config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                return await self._connect_mydevolo(user_input)
            except CredentialsInvalid:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
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
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                return await self._connect_mydevolo(user_input)
            except CredentialsInvalid:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="zeroconf_confirm", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by reauthentication."""
        errors: dict[str, str] = {}
        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=self.init_data[CONF_USERNAME]): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        if user_input is not None:
            try:
                return await self._connect_mydevolo(user_input)
            except CredentialsInvalid:
                errors["base"] = "invalid_auth"
            except UuidChanged:
                errors["base"] = "reauth_failed"

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=data_schema, errors=errors
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

        if self.unique_id != uuid:
            # The old user and the new user are not the same. This could mess-up everything as all unique IDs might change.
            raise UuidChanged

        reauth_entry = self._get_reauth_entry()
        return self.async_update_reload_and_abort(
            reauth_entry, data=user_input, unique_id=uuid
        )
