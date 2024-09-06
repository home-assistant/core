"""Config flow for the jvc_projector integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jvcprojector import JvcProjector, JvcProjectorAuthError, JvcProjectorConnectError
from jvcprojector.projector import DEFAULT_PORT
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.device_registry import format_mac
from homeassistant.util.network import is_host_valid

from .const import DOMAIN, NAME


class JvcProjectorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the JVC Projector integration."""

    VERSION = 1

    _reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user initiated device additions."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            password = user_input.get(CONF_PASSWORD)

            try:
                if not is_host_valid(host):
                    raise InvalidHost  # noqa: TRY301

                mac = await get_mac_address(host, port, password)
            except InvalidHost:
                errors["base"] = "invalid_host"
            except JvcProjectorConnectError:
                errors["base"] = "cannot_connect"
            except JvcProjectorAuthError:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(format_mac(mac))
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: host, CONF_PORT: port, CONF_PASSWORD: password}
                )

                return self.async_create_entry(
                    title=NAME,
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
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth on password authentication error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
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
            data_schema=vol.Schema({vol.Optional(CONF_PASSWORD): str}),
            errors=errors,
        )


class InvalidHost(Exception):
    """Error indicating invalid network host."""


async def get_mac_address(host: str, port: int, password: str | None) -> str:
    """Get device mac address for config flow."""
    device = JvcProjector(host, port=port, password=password)
    try:
        await device.connect(True)
    finally:
        await device.disconnect()
    return device.mac
