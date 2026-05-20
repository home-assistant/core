"""Config flow for Diesel Heater integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_PIN,
    CONF_PRESET_AWAY_TEMP,
    CONF_PRESET_COMFORT_TEMP,
    DEFAULT_PIN,
    DEFAULT_PRESET_AWAY_TEMP,
    DEFAULT_PRESET_COMFORT_TEMP,
    DOMAIN,
    MAX_PIN,
    MIN_PIN,
    SERVICE_UUID,
    SERVICE_UUID_ALT,
)

_LOGGER = logging.getLogger(__name__)


def _normalize_mac_address(address: str) -> str:
    """Normalize MAC address to uppercase with colons.

    Home Assistant expects MAC addresses in format XX:XX:XX:XX:XX:XX.
    """
    # Replace hyphens with colons and convert to uppercase
    normalized = address.upper().replace("-", ":")
    return normalized


class VevorHeaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Diesel Heater."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered Diesel Heater: %s", discovery_info.address)

        await self.async_set_unique_id(_normalize_mac_address(discovery_info.address))
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None

        if user_input is not None:
            address = _normalize_mac_address(self._discovery_info.address)
            return self.async_create_entry(
                title=f"Diesel Heater ({address[-5:].replace(':', '')})",
                data={
                    CONF_ADDRESS: address,
                    CONF_PIN: user_input.get(CONF_PIN, DEFAULT_PIN),
                },
            )

        self._set_confirm_only()

        address = _normalize_mac_address(self._discovery_info.address)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_PIN,
                    default=DEFAULT_PIN
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_PIN, max=MAX_PIN),
                ),
            }),
            description_placeholders={
                "name": f"Diesel Heater ({address[-5:].replace(':', '')})",
                "address": address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = _normalize_mac_address(user_input[CONF_ADDRESS])
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Diesel Heater ({address[-5:].replace(':', '')})",
                data={
                    CONF_ADDRESS: address,
                    CONF_PIN: user_input.get(CONF_PIN, DEFAULT_PIN),
                },
            )

        # Get current bluetooth devices
        current_addresses = self._async_current_ids()

        # Scan for diesel heaters
        discovered = bluetooth.async_discovered_service_info(self.hass)

        _LOGGER.debug("Scanning for diesel heaters, found %d BLE devices", len(discovered))

        for discovery_info in discovered:
            address = _normalize_mac_address(discovery_info.address)

            # Skip already configured devices
            if address in current_addresses or address in self._discovered_devices:
                continue

            # Method 1: Check if device advertises our service UUIDs
            service_uuids_lower = [s.lower() for s in discovery_info.service_uuids]
            has_service_uuid = (
                SERVICE_UUID.lower() in service_uuids_lower
                or SERVICE_UUID_ALT.lower() in service_uuids_lower
            )

            # Method 2: Check for known device names
            device_name = discovery_info.name or ""
            is_heater_name = any(name in device_name.upper() for name in [
                "VEVOR", "HEATER", "AIR HEATER", "DIESEL"
            ])

            # Method 3: Check manufacturer_id 65535 (0xFFFF)
            has_heater_manufacturer = 65535 in discovery_info.manufacturer_data

            _LOGGER.debug(
                "Device %s (%s): service_uuid=%s, name_match=%s, manufacturer=%s",
                address, device_name, has_service_uuid, is_heater_name, has_heater_manufacturer
            )

            # Accept device if any method matches
            if has_service_uuid or is_heater_name or has_heater_manufacturer:
                self._discovered_devices[address] = discovery_info
                _LOGGER.info("Found potential diesel heater: %s (%s)", address, device_name)

        if not self._discovered_devices:
            _LOGGER.warning(
                "No diesel heaters found. Make sure the heater is powered on and within Bluetooth range. "
                "If using ESPHome Bluetooth Proxy, ensure it has available connection slots (max 3 connections)."
            )
            # Allow manual entry if no devices found
            return await self.async_step_manual()

        # Create selection list
        devices = {
            address: f"{info.name or 'Diesel Heater'} ({address})"
            for address, info in self._discovered_devices.items()
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS): vol.In(devices),
                vol.Optional(
                    CONF_PIN,
                    default=DEFAULT_PIN
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_PIN, max=MAX_PIN),
                ),
            }),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual MAC address entry."""
        errors = {}

        if user_input is not None:
            address = _normalize_mac_address(user_input[CONF_ADDRESS])

            # Validate MAC address format
            if not re.match(r"^([0-9A-F]{2}:){5}([0-9A-F]{2})$", address):
                errors[CONF_ADDRESS] = "invalid_mac"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Diesel Heater ({address[-5:].replace(':', '')})",
                    data={
                        CONF_ADDRESS: address,
                        CONF_PIN: user_input.get(CONF_PIN, DEFAULT_PIN),
                    },
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS): str,
                vol.Optional(
                    CONF_PIN,
                    default=DEFAULT_PIN
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_PIN, max=MAX_PIN),
                ),
            }),
            errors=errors,
            description_placeholders={
                "address_format": "XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX",
            }
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return VevorHeaterOptionsFlowHandler()


class VevorHeaterOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Diesel Heater."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Remove empty/None values
            options = {k: v for k, v in user_input.items() if v is not None and v != ""}
            return self.async_create_entry(title="", data=options)

        # Read current values from options (with fallback to data for migration)
        opts = self.config_entry.options
        data = self.config_entry.data

        schema_dict = {
            vol.Optional(
                CONF_PIN,
                default=opts.get(CONF_PIN, data.get(CONF_PIN, DEFAULT_PIN)),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_PIN, max=MAX_PIN),
            ),
            vol.Optional(
                CONF_PRESET_AWAY_TEMP,
                default=opts.get(CONF_PRESET_AWAY_TEMP, data.get(CONF_PRESET_AWAY_TEMP, DEFAULT_PRESET_AWAY_TEMP)),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=8, max=36),
            ),
            vol.Optional(
                CONF_PRESET_COMFORT_TEMP,
                default=opts.get(CONF_PRESET_COMFORT_TEMP, data.get(CONF_PRESET_COMFORT_TEMP, DEFAULT_PRESET_COMFORT_TEMP)),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=8, max=36),
            ),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
