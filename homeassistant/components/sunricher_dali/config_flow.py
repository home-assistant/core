"""Config flow for the Sunricher DALI integration."""

from __future__ import annotations

import logging
from typing import Any

from PySrDaliGateway import DaliGateway
from PySrDaliGateway.discovery import DaliGatewayDiscovery
from PySrDaliGateway.exceptions import DaliGatewayError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_SERIAL_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("refresh", default=False): bool,
    }
)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a options flow for Dali Center."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, bool] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the options flow."""
        if not user_input:
            return self.async_show_form(
                step_id="init",
                data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, {}),
            )

        if user_input.get("refresh", False):
            return await self.async_step_refresh()

        return self.async_create_entry(data={})

    async def async_step_refresh(self) -> ConfigFlowResult:
        """Refresh gateway IP, devices, groups, and scenes."""
        current_sn = self._config_entry.data[CONF_SERIAL_NUMBER]

        try:
            discovery = DaliGatewayDiscovery()
            discovered_gateways = await discovery.discover_gateways(current_sn)
        except DaliGatewayError:
            return self.async_show_form(
                step_id="refresh",
                errors={"base": "cannot_connect"},
                data_schema=vol.Schema({}),
            )

        if not discovered_gateways:
            return self.async_show_form(
                step_id="refresh",
                errors={"base": "gateway_not_found"},
                data_schema=vol.Schema({}),
            )

        if hasattr(self._config_entry, "runtime_data"):
            await self._config_entry.runtime_data.gateway.disconnect()

        updated_gateway = discovered_gateways[0]
        current_data = dict(self._config_entry.data)
        current_data[CONF_HOST] = updated_gateway.gw_ip

        self.hass.config_entries.async_update_entry(
            self._config_entry, data=current_data
        )

        if not await self.hass.config_entries.async_reload(self._config_entry.entry_id):
            return self.async_show_form(
                step_id="refresh",
                errors={"base": "cannot_connect"},
                data_schema=vol.Schema({}),
            )

        return self.async_show_form(
            step_id="refresh_result",
            data_schema=vol.Schema({}),
            description_placeholders={
                "gateway_sn": current_sn,
                "new_ip": updated_gateway.gw_ip,
            },
        )

    async def async_step_refresh_result(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the refresh result step."""
        return self.async_create_entry(data={})


class DaliCenterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sunricher DALI."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

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
                return self.async_create_entry(
                    title=selected_gateway.name,
                    data={
                        CONF_SERIAL_NUMBER: selected_gateway.gw_sn,
                        CONF_HOST: selected_gateway.gw_ip,
                        CONF_PORT: selected_gateway.port,
                        CONF_NAME: selected_gateway.name,
                        CONF_USERNAME: selected_gateway.username,
                        CONF_PASSWORD: selected_gateway.passwd,
                    },
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
