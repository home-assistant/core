"""Config flow for Marstek integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .client import async_get_udp_client
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_MANUAL_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


def _device_from_discovery_result(
    device_info: dict[str, Any], host: str | None = None
) -> dict[str, Any]:
    """Return config flow device data from a discovery response result."""
    device_type = device_info.get("device", "Unknown")
    version = device_info.get("ver", 0)
    ip_address = device_info.get("ip") or host or ""
    wifi_mac = device_info.get("wifi_mac", "")
    ble_mac = device_info.get("ble_mac", "")

    return {
        "id": device_info.get("id", 0),
        "device_type": device_type,
        "version": version,
        "wifi_name": device_info.get("wifi_name", ""),
        "ip": ip_address,
        "wifi_mac": wifi_mac,
        "ble_mac": ble_mac,
        "mac": wifi_mac or ble_mac,
        "model": device_type,
        "firmware": str(version),
    }


def _device_display_name(device: dict[str, Any]) -> str:
    """Return a stable display name for a discovered Marstek device."""
    device_type = device.get("device_type") or device.get("model") or "Marstek"
    version = device.get("version") or device.get("firmware") or "Unknown"
    host = device.get("ip") or "Unknown IP"
    wifi_name = device.get("wifi_name") or "No WiFi"

    return f"{device_type} v{version} ({wifi_name}) - {host}"


class MarstekConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Marstek."""

    VERSION = 1
    domain = DOMAIN
    discovered_devices: list[dict[str, Any]]
    discovered_device_options: dict[str, int]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user",
            menu_options={
                "discover": "Search for devices on the local network",
                "manual": "Enter device IP address",
            },
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle broadcast device discovery."""
        if user_input is not None:
            # User has selected a device from the discovered list
            selected_device = user_input["device"]
            device_index = self.discovered_device_options[selected_device]
            device = self.discovered_devices[device_index]

            return await self._async_create_entry_from_device(device)

        # Start broadcast device discovery
        udp_client = await async_get_udp_client(self.hass)
        try:
            _LOGGER.info("Starting device discovery")

            # Execute broadcast discovery with retry mechanism
            devices = await self._discover_devices_with_retry(udp_client)

            if not devices:
                return self.async_show_form(
                    step_id="discover",
                    data_schema=vol.Schema({}),
                    errors={"base": "no_devices_found"},
                )

            # Store discovered devices for selection
            self.discovered_devices = devices
            _LOGGER.info("Discovered %d devices", len(devices))

            # Show device selection form with detailed device information
            device_options: list[SelectOptionDict] = []
            self.discovered_device_options = {}
            for i, device in enumerate(devices):
                device_name = _device_display_name(device)
                if device_name in self.discovered_device_options:
                    device_name = f"{device_name} #{i + 1}"
                self.discovered_device_options[device_name] = i
                device_options.append(
                    SelectOptionDict(value=device_name, label=device_name)
                )

            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema(
                    {
                        vol.Required("device"): SelectSelector(
                            SelectSelectorConfig(
                                options=device_options,
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        )
                    }
                ),
            )

        except (OSError, TimeoutError, ValueError) as err:
            _LOGGER.error("Device discovery failed: %s", err)
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema({}),
                errors={"base": "discovery_failed"},
            )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual device setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            self._async_abort_entries_match({CONF_HOST: host})

            try:
                device = await self._async_get_device_from_host(host)
            except TimeoutError:
                errors["base"] = "cannot_connect"
            except (OSError, TypeError, ValueError) as err:
                _LOGGER.debug("Manual Marstek setup failed for %s: %s", host, err)
                errors["base"] = "device_not_found"
            else:
                return await self._async_create_entry_from_device(device)

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_get_device_from_host(self, host: str) -> dict[str, Any]:
        """Fetch device information from a specific host."""
        udp_client = await async_get_udp_client(self.hass)
        device_info = await udp_client.get_device_info(host)
        if not isinstance(device_info, dict):
            raise TypeError("No device information returned")
        return _device_from_discovery_result(device_info, host)

    async def _async_create_entry_from_device(
        self, device: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create a config entry from normalized Marstek device data."""
        unique_id = device["mac"] or device["ip"]
        _LOGGER.info(
            "Check device uniqueness: IP=%s, MAC=%s, unique_id=%s",
            device["ip"],
            device["mac"],
            unique_id,
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: device["ip"]})

        title = f"Marstek {device['device_type']} v{device['version']} ({device['ip']})"
        return self.async_create_entry(
            title=title,
            data={
                CONF_HOST: device["ip"],
                CONF_MAC: device["mac"],
                "device_type": device["device_type"],
                "version": device["version"],
                "wifi_name": device["wifi_name"],
                "wifi_mac": device["wifi_mac"],
                "ble_mac": device["ble_mac"],
                "model": device["model"],  # Compatibility field
                "firmware": device["firmware"],  # Compatibility field
            },
        )

    async def _discover_devices_with_retry(
        self, udp_client, max_retries=2, retry_delay=3000
    ):
        """Device discovery retry mechanism."""
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    _LOGGER.info("Device discovery, attempt %d", attempt)
                    await asyncio.sleep(retry_delay / 1000)  # Convert to seconds
                    # Clear cache, force re-discovery
                    udp_client.clear_discovery_cache()

                # First attempt uses cache, retries force refresh
                use_cache = attempt == 1
                devices = await udp_client.discover_devices(use_cache=use_cache)

                if devices:
                    if attempt > 1:
                        _LOGGER.info("Device discovery retry successful")
                    return devices
                _LOGGER.warning("Attempt %d found no devices", attempt)

            except (OSError, TimeoutError, ValueError) as error:
                _LOGGER.error("Device discovery failed, attempt %d: %s", attempt, error)

                if attempt == max_retries:
                    _LOGGER.error(
                        "Device discovery failed after %d retries: %s",
                        max_retries,
                        error,
                    )
                    # Try using cached data as fallback
                    cached_devices = udp_client.get_discovery_cache()
                    if cached_devices:
                        _LOGGER.info("Using cached device data as fallback")
                        return cached_devices
                    raise

        return []
