"""Config flow for the DALI Center integration."""

from __future__ import annotations

import logging
from typing import Any

from PySrDaliGateway import DaliGatewayType
from PySrDaliGateway.discovery import DaliGatewayDiscovery
from PySrDaliGateway.exceptions import DaliGatewayError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_GATEWAY_DATA, CONF_GATEWAY_SN, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DaliCenterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DALI Center."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_gateways: dict[str, DaliGatewayType] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return await self.async_step_discovery()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )

    async def async_step_discovery(
        self, discovery_info: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle gateway discovery."""
        errors: dict[str, str] = {}

        if discovery_info and "selected_gateway" in discovery_info:
            selected_sn = discovery_info["selected_gateway"]
            selected_gateway = self._discovered_gateways.get(selected_sn)

            if selected_gateway:
                await self.async_set_unique_id(selected_gateway["gw_sn"])
                self._abort_if_unique_id_configured()

                title = selected_gateway["name"]

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_GATEWAY_SN: selected_gateway["gw_sn"],
                        CONF_GATEWAY_DATA: selected_gateway,
                    },
                )
            errors["base"] = "device_not_found"

        if not self._discovered_gateways or errors:
            _LOGGER.debug("Starting gateway discovery")
            discovery = DaliGatewayDiscovery()
            try:
                discovered = await discovery.discover_gateways()
            except DaliGatewayError as err:
                _LOGGER.debug("Gateway discovery failed", exc_info=err)
                errors["base"] = "discovery_failed"
            else:
                configured_gateways = {
                    entry.data[CONF_GATEWAY_SN]
                    for entry in self.hass.config_entries.async_entries(DOMAIN)
                }

                self._discovered_gateways = {
                    gw["gw_sn"]: gw
                    for gw in discovered
                    if gw["gw_sn"] not in configured_gateways
                }

        if not self._discovered_gateways:
            return self.async_show_form(
                step_id="discovery",
                errors=errors if errors else {"base": "no_devices_found"},
                data_schema=vol.Schema({}),
            )

        gateway_options = {
            sn: f"{sn} ({gateway['gw_ip']})"
            for sn, gateway in self._discovered_gateways.items()
        }

        return self.async_show_form(
            step_id="discovery",
            data_schema=vol.Schema(
                {
                    vol.Required("selected_gateway"): vol.In(gateway_options),
                }
            ),
            errors=errors,
        )
