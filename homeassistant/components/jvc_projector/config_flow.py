"""Config flow for the JVC Projector integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from jvcprojector import JvcProjectorAuthError, JvcProjectorConnectError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.util.network import is_host_valid

from . import get_mac_address
from .const import DEFAULT_PORT, DOMAIN, NAME

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class JvcProjectorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the JVC Projector integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user initiated device additions."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            password = None
            if CONF_PASSWORD in user_input:
                password = user_input[CONF_PASSWORD]

            try:
                if not is_host_valid(host):
                    raise InvalidHost

                mac = await get_mac_address(host, port, password)
            except InvalidHost:
                errors["base"] = "invalid_host"
            except JvcProjectorConnectError:
                errors["base"] = "cannot_connect"
            except JvcProjectorAuthError:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})

                return self.async_create_entry(
                    title=f"{NAME}",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
            self, user_input: Mapping[str, Any]
    ) -> FlowResult:
        """Perform reauth on password authentication error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        assert self._reauth_entry

        errors = {}

        if user_input is not None:
            host = self._reauth_entry.data[CONF_HOST]
            port = self._reauth_entry.data[CONF_PORT]
            password = user_input[CONF_PASSWORD]

            try:
                await get_mac_address(host, port, password)
            except JvcProjectorConnectError:
                errors["base"] = "cannot_connect"
            except JvcProjectorAuthError:
                errors["base"] = "invalid_auth"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={CONF_HOST: host, CONF_PORT: port, CONF_PASSWORD: password},
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )


class InvalidHost(Exception):
    """Error indicating invalid network host."""
