"""Config flow for Ruuvi Gateway integration."""
from __future__ import annotations

import logging
from typing import Any

import aioruuvigateway.api as gw_api
from aioruuvigateway.excs import CannotConnect, InvalidAuth

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.httpx_client import get_async_client

from . import DOMAIN
from .schemata import CONFIG_SCHEMA, get_config_schema_with_default_host

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ruuvi Gateway."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self.config_schema = CONFIG_SCHEMA

    async def _async_validate(
        self,
        user_input: dict[str, Any],
    ) -> tuple[FlowResult | None, dict[str, str]]:
        """Validate configuration (either discovered or user input)."""
        errors: dict[str, str] = {}

        try:
            async with get_async_client(self.hass) as client:
                resp = await gw_api.get_gateway_history_data(
                    client,
                    host=user_input[CONF_HOST],
                    bearer_token=user_input[CONF_TOKEN],
                )
            await self.async_set_unique_id(
                format_mac(resp.gw_mac), raise_on_progress=False
            )
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: user_input[CONF_HOST]}
            )
            info = {"title": f"Ruuvi Gateway {resp.gw_mac_suffix}"}
            return (
                self.async_create_entry(title=info["title"], data=user_input),
                errors,
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return (None, errors)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle requesting or validating user input."""
        if user_input is not None:
            result, errors = await self._async_validate(user_input)
        else:
            result, errors = None, {}
        if result is not None:
            return result
        return self.async_show_form(
            step_id="user",
            data_schema=self.config_schema,
            errors=(errors or None),
        )

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Prepare configuration for a DHCP discovered Ruuvi Gateway."""
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        self.config_schema = get_config_schema_with_default_host(host=discovery_info.ip)
        return await self.async_step_user()
