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
    SOURCE_DHCP,
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
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

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_hostname: str | None = None
        self._discovered_ip: str | None = None

    async def _async_set_single_instance_unique_id(self) -> None:
        """Assign the unique ID used by this single-instance integration."""
        await self.async_set_unique_id(DOMAIN, raise_on_progress=False)
        self._abort_if_unique_id_configured(error="single_instance_allowed")

    async def _async_test_credentials(
        self, user_input: dict[str, Any]
    ) -> dict[str, str]:
        """Validate credentials against iAqualink."""
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

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a DHCP discovery."""
        await self._async_set_single_instance_unique_id()

        self._discovered_hostname = discovery_info.hostname
        self._discovered_ip = discovery_info.ip

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        if self.source not in (SOURCE_DHCP, SOURCE_REAUTH):
            await self._async_set_single_instance_unique_id()

        errors = {}

        if user_input is not None:
            errors = await self._async_test_credentials(user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        discovery = ""
        if (
            self.source == SOURCE_DHCP
            and self._discovered_hostname is not None
            and self._discovered_ip is not None
        ):
            discovery = (
                "A likely iAquaLink device was discovered on your network at "
                f"{self._discovered_ip} ({self._discovered_hostname}). "
            )

        return self.async_show_form(
            step_id="user",
            data_schema=CREDENTIALS_DATA_SCHEMA,
            description_placeholders={"discovery": discovery},
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

        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            errors = await self._async_test_credentials(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    title=user_input[CONF_USERNAME],
                    data_updates={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=CREDENTIALS_DATA_SCHEMA,
            errors=errors,
        )
