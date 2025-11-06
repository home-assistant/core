"""Config flow for the Sunricher DALI integration."""

from __future__ import annotations

import asyncio
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
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_SERIAL_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Delay constants for reload operations (in seconds)
RELOAD_UNLOAD_DELAY = 2
RELOAD_SETUP_DELAY = 3

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

    async def _reload_with_delay(self) -> bool:
        try:
            await self.hass.config_entries.async_unload(self._config_entry.entry_id)
            await asyncio.sleep(RELOAD_UNLOAD_DELAY)

            result = await self.hass.config_entries.async_setup(
                self._config_entry.entry_id
            )

            if not result:
                return False

            await asyncio.sleep(RELOAD_SETUP_DELAY)

        except (OSError, ValueError, RuntimeError):
            _LOGGER.exception("Error during config entry reload")
            return False

        return True

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
        errors: dict[str, str] = {}

        try:
            current_sn = self._config_entry.data[CONF_SERIAL_NUMBER]

            if hasattr(self._config_entry, "runtime_data"):
                gateway: DaliGateway = self._config_entry.runtime_data.gateway
                await gateway.disconnect()

            discovery = DaliGatewayDiscovery()
            discovered_gateways = await discovery.discover_gateways(current_sn)

            if not discovered_gateways:
                _LOGGER.warning("Gateway %s not found during refresh", current_sn)
                errors["base"] = "gateway_not_found"
                return self.async_show_form(
                    step_id="refresh",
                    errors=errors,
                    data_schema=vol.Schema({}),
                )

            updated_gateway = discovered_gateways[0]

            current_data = dict(self._config_entry.data)
            current_data[CONF_HOST] = updated_gateway.gw_ip

            self.hass.config_entries.async_update_entry(
                self._config_entry, data=current_data
            )

            _LOGGER.info(
                "Gateway %s refreshed with IP %s", current_sn, updated_gateway.gw_ip
            )

            # Remove all devices associated with this config entry before reload
            device_reg = dr.async_get(self.hass)
            entity_reg = er.async_get(self.hass)

            # First, get all devices for this config entry
            devices_to_remove = dr.async_entries_for_config_entry(
                device_reg, self._config_entry.entry_id
            )

            # Remove all devices (this will also remove associated entities)
            for device in devices_to_remove:
                _LOGGER.debug(
                    "Removing device %s (%s) before reload",
                    device.name or "Unknown",
                    device.id,
                )
                device_reg.async_remove_device(device.id)

            entities_to_remove = er.async_entries_for_config_entry(
                entity_reg, self._config_entry.entry_id
            )

            for entity in entities_to_remove:
                _LOGGER.debug("Removing entity %s before reload", entity.entity_id)
                entity_reg.async_remove(entity.entity_id)

            # Wait for reload to complete
            reload_success = await self._reload_with_delay()

            if not reload_success:
                _LOGGER.error("Failed to reload integration after refresh")
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="refresh",
                    errors=errors,
                    data_schema=vol.Schema({}),
                )

            return self.async_show_form(
                step_id="refresh_result",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "gateway_sn": current_sn,
                    "new_ip": updated_gateway.gw_ip,
                    "result_message": (
                        f"Gateway {current_sn} has been refreshed.\n"
                        f"IP address: {updated_gateway.gw_ip}\n\n"
                        "All devices, groups, and scenes have been re-discovered."
                    ),
                },
            )

        except Exception:
            _LOGGER.exception("Error refreshing gateway")
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="refresh",
                errors=errors,
                data_schema=vol.Schema({}),
            )

    async def async_step_refresh_result(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the refresh result step."""
        if user_input is None:
            return self.async_show_form(
                step_id="refresh_result",
                data_schema=vol.Schema({}),
            )

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
