"""Config flow for SMLIGHT Zigbee integration."""

from __future__ import annotations

from typing import Any

from pysmlight import Api2
from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)

STEP_AUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SmlightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMLIGHT Zigbee."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.client: Api2
        self.host: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            self.client = Api2(host, session=async_get_clientsession(self.hass))
            self.host = host

            try:
                if not await self._async_check_auth_required(user_input):
                    return await self._async_complete_entry(user_input)
            except SmlightConnectionError:
                errors["base"] = "cannot_connect"
            except SmlightAuthError:
                return await self.async_step_auth()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle authentication to SLZB-06 device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                if not await self._async_check_auth_required(user_input):
                    return await self._async_complete_entry(user_input)
            except SmlightConnectionError:
                return self.async_abort(reason="cannot_connect")
            except SmlightAuthError:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="auth", data_schema=STEP_AUTH_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered Lan coordinator."""
        local_name = discovery_info.hostname[:-1]
        node_name = local_name.removesuffix(".local")

        self.host = local_name
        self.context["title_placeholders"] = {CONF_NAME: node_name}
        self.client = Api2(self.host, session=async_get_clientsession(self.hass))

        mac = discovery_info.properties.get("mac")
        # fallback for legacy firmware
        if mac is None:
            info = await self.client.get_info()
            mac = info.MAC
        await self.async_set_unique_id(format_mac(mac))
        self._abort_if_unique_id_configured()

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery confirm."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_HOST] = self.host
            try:
                if not await self._async_check_auth_required(user_input):
                    return await self._async_complete_entry(user_input)

            except SmlightConnectionError:
                return self.async_abort(reason="cannot_connect")

            except SmlightAuthError:
                return await self.async_step_auth()

        self._set_confirm_only()

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={"host": self.host},
            errors=errors,
        )

    async def _async_check_auth_required(self, user_input: dict[str, Any]) -> bool:
        """Check if auth required and attempt to authenticate."""
        if await self.client.check_auth_needed():
            if user_input.get(CONF_USERNAME) and user_input.get(CONF_PASSWORD):
                return not await self.client.authenticate(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            raise SmlightAuthError
        return False

    async def _async_complete_entry(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        info = await self.client.get_info()
        await self.async_set_unique_id(format_mac(info.MAC))
        self._abort_if_unique_id_configured()

        if user_input.get(CONF_HOST) is None:
            user_input[CONF_HOST] = self.host

        assert info.model is not None
        return self.async_create_entry(title=info.model, data=user_input)
