"""Config flow for the Sunricher DALI integration."""

from __future__ import annotations

import logging
from typing import Any

from PySrDaliGateway import DaliGateway
from PySrDaliGateway.discovery import DaliGatewayDiscovery
from PySrDaliGateway.exceptions import DaliGatewayError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_MAC, CONF_SERIAL_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DaliCenterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sunricher DALI."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_gateways: dict[str, DaliGateway] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return await self.async_step_select_gateway()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )

    async def async_step_select_gateway(
        self, discovery_info: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle gateway discovery."""
        errors: dict[str, str] = {}

        if discovery_info and "selected_gateway" in discovery_info:
            selected_sn = discovery_info["selected_gateway"]
            selected_gateway = self._discovered_gateways[selected_sn]

            await self.async_set_unique_id(selected_gateway.gw_sn)
            self._abort_if_unique_id_configured()

            try:
                await selected_gateway.connect()
            except DaliGatewayError as err:
                _LOGGER.debug(
                    "Failed to connect to gateway %s during config flow",
                    selected_gateway.gw_sn,
                    exc_info=err,
                )
                errors["base"] = "cannot_connect"
            else:
                await selected_gateway.disconnect()
                # MAC address will be populated by DHCP discovery if available
                # or can be added later when DHCP sees the device
                data = {
                    CONF_SERIAL_NUMBER: selected_gateway.gw_sn,
                    CONF_HOST: selected_gateway.gw_ip,
                    CONF_PORT: selected_gateway.port,
                    CONF_NAME: selected_gateway.name,
                    CONF_USERNAME: selected_gateway.username,
                    CONF_PASSWORD: selected_gateway.passwd,
                }
                # MAC address may already be set if coming from DHCP discovery
                # Check if we have it in the discovered gateway (though current library doesn't provide it)
                return self.async_create_entry(
                    title=selected_gateway.name,
                    data=data,
                )

        if not self._discovered_gateways:
            _LOGGER.debug("Starting gateway discovery")
            discovery = DaliGatewayDiscovery()
            try:
                discovered = await discovery.discover_gateways()
            except DaliGatewayError as err:
                _LOGGER.debug("Gateway discovery failed", exc_info=err)
                errors["base"] = "discovery_failed"
            else:
                configured_gateways = {
                    entry.data[CONF_SERIAL_NUMBER]
                    for entry in self.hass.config_entries.async_entries(DOMAIN)
                }

                self._discovered_gateways = {
                    gw.gw_sn: gw
                    for gw in discovered
                    if gw.gw_sn not in configured_gateways
                }

        if not self._discovered_gateways:
            return self.async_show_form(
                step_id="select_gateway",
                errors=errors if errors else {"base": "no_devices_found"},
                data_schema=vol.Schema({}),
            )

        gateway_options = [
            SelectOptionDict(
                value=sn,
                label=f"{gateway.name} [SN {sn}, IP {gateway.gw_ip}]",
            )
            for sn, gateway in self._discovered_gateways.items()
        ]

        return self.async_show_form(
            step_id="select_gateway",
            data_schema=vol.Schema(
                {
                    vol.Optional("selected_gateway"): SelectSelector(
                        SelectSelectorConfig(options=gateway_options, sort=True)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        mac_address = format_mac(discovery_info.macaddress)
        current_ip = discovery_info.ip

        _LOGGER.debug(
            "DHCP discovered device at %s with MAC %s", current_ip, mac_address
        )

        # Try to discover gateways to get serial number from the discovered IP
        discovery = DaliGatewayDiscovery()
        try:
            discovered = await discovery.discover_gateways()
        except DaliGatewayError as err:
            _LOGGER.debug("Gateway discovery failed during DHCP flow", exc_info=err)
            return self.async_abort(reason="discovery_failed")

        # Find the gateway at the DHCP discovered IP
        gateway = None
        for gw in discovered:
            if gw.gw_ip == current_ip:
                gateway = gw
                break

        if not gateway:
            _LOGGER.debug("No gateway found at DHCP discovered IP %s", current_ip)
            return self.async_abort(reason="discovery_failed")

        # Set unique ID and update IP/MAC if entry already exists
        await self.async_set_unique_id(gateway.gw_sn)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: current_ip, CONF_MAC: mac_address}
        )

        # Store gateway for the next step
        self._discovered_gateways = {gateway.gw_sn: gateway}

        # Continue with normal flow
        return await self.async_step_select_gateway()
