"""Config flow for SVS Subwoofer integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN, SVS_SERVICE_UUID

_LOGGER = logging.getLogger(__name__)

# Known SVS device name patterns (OUI prefix for SVS)
SVS_MAC_PREFIX = "08:EB:ED"


class SVSSubwooferConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for SVS Subwoofer."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery.

        This is called when HA discovers a device matching our manifest.json
        bluetooth matchers.
        """
        _LOGGER.debug("Bluetooth discovery: %s", discovery_info)

        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or "SVS Subwoofer"
        }

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Bluetooth device setup."""
        if self._discovery_info is None:  # pragma: no cover - reachable only if the
            # bluetooth_confirm step is invoked without a prior async_step_bluetooth
            return self.async_abort(reason="no_device")

        if user_input is not None:
            name = user_input.get(
                CONF_NAME, self._discovery_info.name or "SVS Subwoofer"
            )
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_NAME: name,
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME, default=self._discovery_info.name or "SVS Subwoofer"
                    ): str,
                }
            ),
            description_placeholders={
                "name": self._discovery_info.name or "SVS Subwoofer",
                "address": self._discovery_info.address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-initiated configuration.

        Shows discovered devices or allows manual MAC entry.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input.get(CONF_ADDRESS, "")

            # Check if user selected a discovered device or entered manual address
            if address in self._discovered_devices:
                # User selected a discovered device
                device = self._discovered_devices[address]
                formatted_mac = format_mac(address)
                await self.async_set_unique_id(formatted_mac)
                self._abort_if_unique_id_configured()

                # Use device name if user didn't provide a custom name
                user_name = user_input.get(CONF_NAME, "")
                final_name = user_name or (device.name or "SVS Subwoofer")

                return self.async_create_entry(
                    title=final_name,
                    data={
                        CONF_ADDRESS: address,
                        CONF_NAME: final_name,
                    },
                )
            # The picker schema only allows addresses from the discovered list
            # or the literal "manual" sentinel — nothing else can reach here.
            return await self.async_step_manual()

        # Discover Bluetooth devices - show all devices with names
        # Prioritize SVS devices (by MAC prefix or service UUID)
        current_addresses = self._async_current_ids()
        svs_devices: dict[str, BluetoothServiceInfoBleak] = {}
        other_devices: dict[str, BluetoothServiceInfoBleak] = {}

        for info in async_discovered_service_info(self.hass):
            if (
                format_mac(info.address) in current_addresses
            ):  # pragma: no cover - covered indirectly via state changes
                continue
            # Skip devices without names (harder to identify)
            if not info.name or info.name == info.address:
                continue

            # Check if this is an SVS device by service UUID or MAC prefix
            service_uuids_lower = [s.lower() for s in info.service_uuids]
            is_svs = (
                SVS_SERVICE_UUID.lower() in service_uuids_lower
                or info.address.upper().startswith(SVS_MAC_PREFIX)
            )

            if is_svs:
                svs_devices[info.address] = info
                _LOGGER.debug("Found SVS device: %s (%s)", info.name, info.address)
            else:
                other_devices[info.address] = info
                _LOGGER.debug("Found other device: %s (%s)", info.name, info.address)

        # Combine: SVS devices first, then others
        self._discovered_devices = {**svs_devices, **other_devices}

        if self._discovered_devices:
            # Show picker with discovered devices
            # Mark SVS devices with a prefix for clarity
            addresses = {}
            for addr, info in self._discovered_devices.items():
                is_svs = addr.upper().startswith(SVS_MAC_PREFIX)
                prefix = "[SVS] " if is_svs else ""
                addresses[addr] = f"{prefix}{info.name or 'Unknown'} ({addr})"

            addresses["manual"] = "Enter MAC address manually..."

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ADDRESS): vol.In(addresses),
                        vol.Optional(CONF_NAME, default=""): str,
                    }
                ),
                errors=errors,
                description_placeholders={
                    "hint": "Leave name blank to use the device's advertised name"
                },
            )

        # No devices found - go straight to manual entry
        return await self.async_step_manual()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual MAC address entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input.get(CONF_ADDRESS, "").upper().replace("-", ":")

            # Validate MAC address format
            mac_clean = address.replace(":", "")
            if len(mac_clean) != 12 or not all(
                c in "0123456789ABCDEF" for c in mac_clean
            ):
                errors[CONF_ADDRESS] = "invalid_mac"
            else:
                formatted_mac = format_mac(address)
                await self.async_set_unique_id(formatted_mac)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "SVS Subwoofer"),
                    data={
                        CONF_ADDRESS: address,
                        CONF_NAME: user_input.get(CONF_NAME, "SVS Subwoofer"),
                    },
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): str,
                    vol.Optional(CONF_NAME, default="SVS Subwoofer"): str,
                }
            ),
            errors=errors,
            description_placeholders={"mac_format": "AA:BB:CC:DD:EE:FF"},
        )
