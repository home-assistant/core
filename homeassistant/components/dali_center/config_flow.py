"""Config flow for the Dali Center integration."""

from __future__ import annotations

import logging
from typing import Any

from PySrDaliGateway import DaliGateway, DeviceType
from PySrDaliGateway.discovery import DaliGatewayDiscovery
from PySrDaliGateway.exceptions import DaliGatewayError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    try:
        gateway = DaliGateway(data["gateway"])
        await gateway.connect()
        gateway_info = gateway.to_dict()
        await gateway.disconnect()

    except DaliGatewayError as err:
        _LOGGER.error("Failed to connect to gateway: %s", err)
        raise CannotConnect from err
    except Exception as err:
        _LOGGER.exception("Unexpected error validating gateway")
        raise CannotConnect from err

    return {
        "title": gateway.name,
        "gateway_info": gateway_info,
    }


class DaliCenterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dali Center."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_gateways: list[Any] = []
        self._selected_gateway: dict[str, Any] | None = None
        self._discovered_devices: list[DeviceType] = []

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

        if discovery_info is not None and "selected_gateway" in discovery_info:
            selected_sn = discovery_info["selected_gateway"]
            selected_gateway = next(
                (gw for gw in self._discovered_gateways if gw["gw_sn"] == selected_sn),
                None,
            )

            if selected_gateway:
                try:
                    info = await validate_input(
                        self.hass, {"gateway": selected_gateway}
                    )
                    await self.async_set_unique_id(selected_gateway["gw_sn"])
                    self._abort_if_unique_id_configured()

                    # Discover devices automatically
                    devices = []
                    gateway = DaliGateway(selected_gateway)
                    await gateway.connect()
                    devices = await gateway.discover_devices()
                    await gateway.disconnect()
                    _LOGGER.debug(
                        "Found %d devices on gateway %s",
                        len(devices),
                        selected_gateway["gw_sn"],
                    )

                    return self.async_create_entry(
                        title=info["title"],
                        data={
                            "sn": selected_gateway["gw_sn"],
                            "gateway": selected_gateway,
                            "devices": devices,
                        },
                    )
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
            else:
                errors["base"] = "device_not_found"

        if not self._discovered_gateways or errors:
            try:
                _LOGGER.debug("Starting gateway discovery")
                discovery = DaliGatewayDiscovery()
                discovered = await discovery.discover_gateways()

                configured_gateways = {
                    entry.data["sn"]
                    for entry in self.hass.config_entries.async_entries(DOMAIN)
                }

                self._discovered_gateways = [
                    gw for gw in discovered if gw["gw_sn"] not in configured_gateways
                ]

            except DaliGatewayError:
                _LOGGER.exception("Gateway discovery failed")
                errors["base"] = "discovery_failed"

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


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
