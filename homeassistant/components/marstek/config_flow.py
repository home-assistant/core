"""Config flow for Marstek integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pymarstek import MarstekUDPClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MarstekConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Marstek."""

    VERSION = 1
    domain = DOMAIN
    discovered_devices: list[dict[str, Any]]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step - broadcast device discovery."""
        if user_input is not None:
            # User has selected a device from the discovered list
            device_index = int(user_input["device"])
            device = self.discovered_devices[device_index]

            # Check if device is already configured using host/mac
            self._async_abort_entries_match({CONF_HOST: device["ip"]})
            if device.get("mac"):
                self._async_abort_entries_match({CONF_MAC: device["mac"]})
                # Use MAC address as unique_id if available
                await self.async_set_unique_id(format_mac(device["mac"]))
                self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Marstek {device['device_type']} ({device['ip']})",
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

        # Start broadcast device discovery
        try:
            _LOGGER.info("Starting device discovery")
            udp_client = MarstekUDPClient()
            await udp_client.async_setup()

            # Execute broadcast discovery with retry mechanism
            devices = await self._discover_devices_with_retry(udp_client)
            await udp_client.async_cleanup()

            if not devices:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({}),
                    errors={"base": "no_devices_found"},
                )

            # Store discovered devices for selection
            self.discovered_devices = devices
            _LOGGER.info("Discovered %d devices", len(devices))

            # Show device selection form with detailed device information
            device_options = {}
            for i, device in enumerate(devices):
                # Build detailed device display name with all important info
                device_name = (
                    f"{device.get('device_type', 'Unknown')} "
                    f"v{device.get('version', 'Unknown')} "
                    f"({device.get('wifi_name', 'No WiFi')}) "
                    f"- {device.get('ip', 'Unknown')}"
                )
                device_options[str(i)] = device_name

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required("device"): vol.In(device_options)}
                ),
                description_placeholders={
                    "devices": "\n".join(
                        [f"- {name}" for name in device_options.values()]
                    )
                },
            )

        except (OSError, TimeoutError, ValueError) as err:
            _LOGGER.error("Device discovery failed: %s", err)
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors={"base": "discovery_failed"},
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
                    if udp_client._discovery_cache:  # noqa: SLF001 - internal access needed for fallback
                        _LOGGER.info("Using cached device data as fallback")
                        return udp_client._discovery_cache.copy()  # noqa: SLF001 - internal access needed for fallback
                    raise

        return []
