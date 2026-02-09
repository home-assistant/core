"""Config flow for Vevor Diesel Heater integration."""
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

from homeassistant.helpers import selector

from .const import (
    CONF_AUTO_OFFSET_MAX,
    CONF_EXTERNAL_TEMP_SENSOR,
    CONF_PIN,
    CONF_PRESET_AWAY_TEMP,
    CONF_PRESET_COMFORT_TEMP,
    DEFAULT_AUTO_OFFSET_MAX,
    DEFAULT_PIN,
    DEFAULT_PRESET_AWAY_TEMP,
    DEFAULT_PRESET_COMFORT_TEMP,
    DOMAIN,
    MAX_AUTO_OFFSET_MAX,
    MAX_PIN,
    MIN_AUTO_OFFSET_MAX,
    MIN_PIN,
    SERVICE_UUID,
)

_LOGGER = logging.getLogger(__name__)


class VevorHeaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vevor Diesel Heater."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered Vevor Heater: %s", discovery_info.address)

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None

        if user_input is not None:
            return self.async_create_entry(
                title=f"Vevor Heater {self._discovery_info.address[-5:].replace(':', '')}",
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_PIN: user_input.get(CONF_PIN, DEFAULT_PIN),
                },
            )

        self._set_confirm_only()

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
                "name": f"Vevor Heater {self._discovery_info.address[-5:].replace(':', '')}"
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Vevor Heater {address[-5:].replace(':', '')}",
                data={
                    CONF_ADDRESS: address,
                    CONF_PIN: user_input.get(CONF_PIN, DEFAULT_PIN),
                },
            )

        # Get current bluetooth devices
        current_addresses = self._async_current_ids()

        # Scan for Vevor heaters
        discovered = bluetooth.async_discovered_service_info(self.hass)

        _LOGGER.debug("Scanning for Vevor heaters, found %d BLE devices", len(discovered))

        # Add explicit check for known Vevor heater MAC address A4:C1:37:24:B8:64
        for discovery_info in discovered:
            address = discovery_info.address

            # Skip already configured devices
            if address in current_addresses or address in self._discovered_devices:
                continue

            # Method 1: Check if device advertises our service UUID
            has_service_uuid = SERVICE_UUID.lower() in [
                service.lower() for service in discovery_info.service_uuids
            ]

            # Method 2: Check for known Vevor device names
            device_name = discovery_info.name or ""
            is_vevor_name = any(name in device_name.upper() for name in [
                "VEVOR", "HEATER", "AIR HEATER", "DIESEL"
            ])

            # Method 3: Check manufacturer_id 65535 (0xFFFF)
            has_vevor_manufacturer = 65535 in discovery_info.manufacturer_data

            _LOGGER.debug(
                "Device %s (%s): service_uuid=%s, name_match=%s, manufacturer=%s",
                address, device_name, has_service_uuid, is_vevor_name, has_vevor_manufacturer
            )

            # Accept device if any method matches
            if has_service_uuid or is_vevor_name or has_vevor_manufacturer:
                self._discovered_devices[address] = discovery_info
                _LOGGER.info("Found potential Vevor heater: %s (%s)", address, device_name)

        if not self._discovered_devices:
            _LOGGER.warning(
                "No Vevor heaters found. Make sure the heater is powered on and within Bluetooth range. "
                "If using ESPHome Bluetooth Proxy, ensure it has available connection slots (max 3 connections)."
            )
            # Allow manual entry if no devices found
            return await self.async_step_manual()

        # Create selection list
        devices = {
            address: f"{info.name or 'Vevor Heater'} ({address})"
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
            address = user_input[CONF_ADDRESS].upper()

            # Validate MAC address format
            if not re.match(r"^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$", address):
                errors[CONF_ADDRESS] = "invalid_mac"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Vevor Heater {address[-5:].replace(':', '')}",
                    data={
                        CONF_ADDRESS: address,
                        CONF_PIN: user_input.get(CONF_PIN, DEFAULT_PIN),
                    },
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS, description="Bluetooth MAC Address (e.g., A4:C1:37:24:B8:64)"): str,
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
                "info": "Enter the Bluetooth MAC address of your Vevor heater. "
                        "You can find this in your Home Assistant Bluetooth logs or using a BLE scanner app."
            }
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return VevorHeaterOptionsFlowHandler()


class VevorHeaterOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Vevor Heater."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Handle clearing of external sensor
            # EntitySelector returns None when cleared, store as empty string
            if CONF_EXTERNAL_TEMP_SENSOR not in user_input or user_input.get(CONF_EXTERNAL_TEMP_SENSOR) is None:
                user_input[CONF_EXTERNAL_TEMP_SENSOR] = ""
                # Also clear auto_offset_max when sensor is cleared
                user_input.pop(CONF_AUTO_OFFSET_MAX, None)

            # Update config entry with new settings
            # Merge with existing data, but remove keys that were cleared
            new_data = {**self.config_entry.data}
            for key, value in user_input.items():
                if value == "" or value is None:
                    new_data.pop(key, None)
                else:
                    new_data[key] = value

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
            )
            return self.async_create_entry(title="", data={})

        # Get current external sensor value (may be empty string or None)
        current_external_sensor = self.config_entry.data.get(CONF_EXTERNAL_TEMP_SENSOR)
        # EntitySelector expects None for empty, not empty string
        if not current_external_sensor:
            current_external_sensor = None

        # Build schema - only show auto_offset_max if external sensor is configured
        schema_dict = {
            vol.Optional(
                CONF_PIN,
                default=self.config_entry.data.get(CONF_PIN, DEFAULT_PIN)
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_PIN, max=MAX_PIN),
            ),
            vol.Optional(
                CONF_PRESET_AWAY_TEMP,
                default=self.config_entry.data.get(CONF_PRESET_AWAY_TEMP, DEFAULT_PRESET_AWAY_TEMP)
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=8, max=36),
            ),
            vol.Optional(
                CONF_PRESET_COMFORT_TEMP,
                default=self.config_entry.data.get(CONF_PRESET_COMFORT_TEMP, DEFAULT_PRESET_COMFORT_TEMP)
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=8, max=36),
            ),
            vol.Optional(
                CONF_EXTERNAL_TEMP_SENSOR,
                description={"suggested_value": current_external_sensor}
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="temperature",
                )
            ),
        }

        # Only show auto_offset_max if external sensor is configured
        if current_external_sensor:
            schema_dict[vol.Optional(
                CONF_AUTO_OFFSET_MAX,
                default=self.config_entry.data.get(CONF_AUTO_OFFSET_MAX, DEFAULT_AUTO_OFFSET_MAX)
            )] = vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_AUTO_OFFSET_MAX, max=MAX_AUTO_OFFSET_MAX),
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "note": "To clear the external temperature sensor, leave the field empty."
            }
        )
