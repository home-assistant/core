"""Config flow for the Dali Center integration."""

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
    """Handle a config flow for Dali Center."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_gateways: list[DaliGatewayType] = []

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
            selected_gateway: DaliGatewayType | None = next(
                (gw for gw in self._discovered_gateways if gw["gw_sn"] == selected_sn),
                None,
            )

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

                self._discovered_gateways = [
                    gw for gw in discovered if gw["gw_sn"] not in configured_gateways
                ]

        if not self._discovered_gateways:
            return self.async_show_form(
                step_id="discovery",
                errors=errors if errors else {"base": "no_devices_found"},
                data_schema=vol.Schema({}),
            )

        gateway_options = {
            gw["gw_sn"]: f"{gw['gw_sn']} ({gw['gw_ip']})"
            for gw in self._discovered_gateways
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
