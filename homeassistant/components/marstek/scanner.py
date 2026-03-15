"""Scanner for Marstek devices - detects IP changes."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, ClassVar, Self

from pymarstek import MarstekUDPClient

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Scanner runs discovery every 60 seconds to detect IP changes
SCAN_INTERVAL = timedelta(seconds=60)


class MarstekScanner:
    """Scanner for Marstek devices that detects IP address changes."""

    _scanner: ClassVar[Self | None] = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the scanner."""
        self._hass = hass
        self._track_interval: CALLBACK_TYPE | None = None

    @classmethod
    @callback
    def async_get(cls, hass: HomeAssistant) -> Self:
        """Get singleton scanner instance."""
        if cls._scanner is None:
            cls._scanner = cls(hass)
        return cls._scanner

    async def async_setup(self) -> None:
        """Initialize scanner and start periodic scanning."""
        _LOGGER.info("Initializing Marstek scanner")
        # No need to create persistent UDP client - create new instance for each scan
        # This avoids state issues and conflicts with concurrent requests

        # Start periodic scanning
        self._track_interval = async_track_time_interval(
            self._hass,
            self.async_scan,
            SCAN_INTERVAL,
            cancel_on_shutdown=True,
        )

        # Execute initial scan immediately
        self.async_scan()

    @callback
    def async_scan(self, now=None) -> None:
        """Periodically scan for devices and check IP changes."""
        # Execute scan in background task (non-blocking)
        self._hass.async_create_task(self._async_scan_impl())

    async def _async_scan_impl(self) -> None:
        """Execute device discovery and check for IP changes."""
        # Create a new UDP client instance for each scan (same as config_flow)
        # This avoids state issues with persistent client and potential conflicts
        # with concurrent requests from Coordinator
        udp_client = MarstekUDPClient()
        try:
            await udp_client.async_setup()

            # Always use broadcast discovery (use_cache=False) for Scanner
            # Scanner needs to detect latest device state and IP changes
            # Unlike config_flow which can use cache for initial setup
            _LOGGER.debug("Scanner: Starting device discovery (broadcast)")
            devices = await udp_client.discover_devices(use_cache=False)

            _LOGGER.debug(
                "Scanner: Discovered %d device(s)", len(devices) if devices else 0
            )

            if not devices:
                return

            # Log discovered devices for debugging
            _LOGGER.debug("Scanner: Discovered devices:")
            for device in devices:
                _LOGGER.debug(
                    "  Device: %s at IP %s (BLE-MAC: %s)",
                    device.get("device_type", "Unknown"),
                    device.get("ip", "Unknown"),
                    device.get("ble_mac", "N/A"),
                )

            # Check all configured entries for IP changes
            # Check both LOADED and SETUP_RETRY states (SETUP_RETRY means connection failed)
            for entry in self._hass.config_entries.async_entries(DOMAIN):
                _LOGGER.debug(
                    "Scanner: Checking entry %s (state: %s)",
                    entry.title,
                    entry.state,
                )
                if entry.state not in (
                    ConfigEntryState.LOADED,
                    ConfigEntryState.SETUP_RETRY,
                ):
                    _LOGGER.debug(
                        "Scanner: Skipping entry %s - state is %s (not LOADED)",
                        entry.title,
                        entry.state,
                    )
                    continue

                stored_ble_mac = entry.data.get("ble_mac")
                stored_ip = entry.data.get(CONF_HOST)

                _LOGGER.debug(
                    "Scanner: Entry %s - stored BLE-MAC: %s, stored IP: %s",
                    entry.title,
                    stored_ble_mac or "N/A",
                    stored_ip or "N/A",
                )

                if not stored_ble_mac or not stored_ip:
                    _LOGGER.debug(
                        "Scanner: Skipping entry %s - missing BLE-MAC or IP",
                        entry.title,
                    )
                    continue

                # Find matching device by BLE-MAC
                matched_device = self._find_device_by_ble_mac(
                    devices, stored_ble_mac, entry.title
                )

                if not matched_device:
                    _LOGGER.debug(
                        "Scanner: No matching device found for entry %s (BLE-MAC: %s)",
                        entry.title,
                        stored_ble_mac,
                    )
                    continue

                new_ip = matched_device.get("ip")
                _LOGGER.debug(
                    "Scanner: Entry %s - current IP: %s, discovered IP: %s",
                    entry.title,
                    stored_ip,
                    new_ip,
                )
                if new_ip and new_ip != stored_ip:
                    _LOGGER.info(
                        "Scanner detected IP change for device %s: %s -> %s",
                        stored_ble_mac,
                        stored_ip,
                        new_ip,
                    )
                    # Trigger discovery flow to update config entry (mik-laj feedback)
                    # This follows the pattern used in Yeelight integration
                    discovery_flow.async_create_flow(
                        self._hass,
                        DOMAIN,
                        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                        data={
                            "ip": new_ip,
                            "ble_mac": stored_ble_mac,
                            "device_type": matched_device.get("device_type"),
                            "version": matched_device.get("version"),
                            "wifi_name": matched_device.get("wifi_name"),
                            "wifi_mac": matched_device.get("wifi_mac"),
                            "mac": matched_device.get("mac"),
                        },
                    )
                else:
                    _LOGGER.debug(
                        "Scanner: Entry %s IP unchanged (%s)",
                        entry.title,
                        stored_ip,
                    )
        except Exception as err:  # noqa: BLE001 - Scanner runs in background, catch all errors
            _LOGGER.debug("Scanner discovery failed: %s", err)
        finally:
            # Clean up UDP client (same as config_flow)
            await udp_client.async_cleanup()

    def _find_device_by_ble_mac(
        self, devices: list[dict[str, Any]], stored_ble_mac: str, entry_title: str
    ) -> dict[str, Any] | None:
        """Find device by BLE-MAC address."""
        for device in devices:
            device_ble_mac = device.get("ble_mac")
            if device_ble_mac:
                _LOGGER.debug(
                    "Scanner: Comparing stored BLE-MAC %s with device BLE-MAC %s",
                    format_mac(stored_ble_mac),
                    format_mac(device_ble_mac),
                )
                if format_mac(device_ble_mac) == format_mac(stored_ble_mac):
                    _LOGGER.debug(
                        "Scanner: BLE-MAC match found for entry %s",
                        entry_title,
                    )
                    return device
        return None
