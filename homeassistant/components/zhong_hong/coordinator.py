"""DataUpdateCoordinator for ZhongHong integration."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta
import logging
from typing import Any

from zhong_hong_hvac.hub import ZhongHongGateway
from zhong_hong_hvac.hvac import HVAC as ZhongHongHVAC

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_GATEWAY_ADDRESS,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ZhongHongDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching ZhongHong data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data[CONF_PORT]
        self.gateway_address = entry.data.get(CONF_GATEWAY_ADDRESS, 1)

        self.hub = ZhongHongGateway(self.host, self.port, self.gateway_address)
        self.devices: dict[str, ZhongHongHVAC] = {}
        self._hub_connected = False
        self._reconnect_task: asyncio.Task | None = None
        self._stop_reconnect = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    def hub_connected(self) -> bool:
        """Return the current connection status of the hub."""
        return self._hub_connected

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        if not self._hub_connected:
            await self._async_connect_hub()

        try:
            # Query all device status
            await self.hass.async_add_executor_job(self.hub.query_all_status)

            # Collect device data
            data = {}
            for device_id, device in self.devices.items():
                data[device_id] = {
                    "current_operation": getattr(device, "current_operation", None),
                    "current_temperature": getattr(device, "current_temperature", None),
                    "target_temperature": getattr(device, "target_temperature", None),
                    "current_fan_mode": getattr(device, "current_fan_mode", None),
                    "is_on": getattr(device, "is_on", False),
                }

        except Exception as err:
            _LOGGER.error("Error updating ZhongHong data: %s", err)
            self._hub_connected = False
            # Start reconnection process
            if not self._reconnect_task or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._async_reconnect_loop())
            raise UpdateFailed(
                f"Error communicating with ZhongHong gateway: {err}"
            ) from err
        else:
            return data

    async def async_config_entry_first_refresh(self) -> None:
        """Perform first refresh and device discovery."""
        await self._async_discover_devices()
        await super().async_config_entry_first_refresh()

    async def _async_discover_devices(self) -> None:
        """Discover devices connected to the gateway."""
        try:
            discovered = await self.hass.async_add_executor_job(self.hub.discovery_ac)

            for addr_out, addr_in in discovered:
                device_id = f"{addr_out}_{addr_in}"
                device = ZhongHongHVAC(self.hub, addr_out, addr_in)
                self.devices[device_id] = device
                _LOGGER.debug("Discovered device: %s", device_id)

            _LOGGER.info("Discovered %d ZhongHong devices", len(self.devices))

        except Exception as err:
            _LOGGER.error("Failed to discover devices: %s", err)
            raise

    async def _async_connect_hub(self) -> None:
        """Connect to the hub with retry logic."""
        for attempt in range(DEFAULT_RETRY_COUNT):
            try:
                await self.hass.async_add_executor_job(self.hub.start_listen)
                self._hub_connected = True
                _LOGGER.info("Successfully connected to ZhongHong gateway")
            except OSError as err:
                _LOGGER.warning(
                    "Failed to connect to ZhongHong gateway (attempt %d/%d): %s",
                    attempt + 1,
                    DEFAULT_RETRY_COUNT,
                    err,
                )
                if attempt < DEFAULT_RETRY_COUNT - 1:
                    await asyncio.sleep(DEFAULT_RETRY_DELAY)
            else:
                return

        raise UpdateFailed("Failed to connect to ZhongHong gateway after retries")

    async def _async_reconnect_loop(self) -> None:
        """Continuous reconnection loop."""
        while not self._stop_reconnect and not self._hub_connected:
            try:
                _LOGGER.info("Attempting to reconnect to ZhongHong gateway")
                await self._async_connect_hub()
                if self._hub_connected:
                    _LOGGER.info("Reconnected to ZhongHong gateway successfully")
                    # Trigger a data update
                    await self.async_request_refresh()
                    break

            except OSError as err:
                _LOGGER.debug("Reconnection attempt failed: %s", err)

            await asyncio.sleep(DEFAULT_RETRY_DELAY)

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        self._stop_reconnect = True

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task

        if self._hub_connected:
            try:
                await self.hass.async_add_executor_job(self.hub.stop_listen)
                _LOGGER.info("ZhongHong gateway connection closed")
            except OSError as err:
                _LOGGER.debug("Error closing gateway connection: %s", err)

    async def async_send_command(
        self, device_id: str, command: str, *args, **kwargs
    ) -> bool:
        """Send command to device with retry logic."""
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.error("Device %s not found", device_id)
            return False

        if not self._hub_connected:
            _LOGGER.warning("Hub not connected, attempting to reconnect")
            await self._async_connect_hub()

        for attempt in range(DEFAULT_RETRY_COUNT):
            try:
                method = getattr(device, command)
                await self.hass.async_add_executor_job(method, *args, **kwargs)
                _LOGGER.debug("Command %s sent to device %s", command, device_id)

            except OSError as err:
                _LOGGER.warning(
                    "Failed to send command %s to device %s (attempt %d/%d): %s",
                    command,
                    device_id,
                    attempt + 1,
                    DEFAULT_RETRY_COUNT,
                    err,
                )

                if attempt < DEFAULT_RETRY_COUNT - 1:
                    # Try to reconnect before next attempt
                    self._hub_connected = False
                    try:
                        await self._async_connect_hub()
                    except OSError:
                        await asyncio.sleep(DEFAULT_RETRY_DELAY)
                        continue
                else:
                    # Last attempt failed, start reconnection process
                    self._hub_connected = False
                    if not self._reconnect_task or self._reconnect_task.done():
                        self._reconnect_task = asyncio.create_task(
                            self._async_reconnect_loop()
                        )
            else:
                return True

        _LOGGER.error(
            "Failed to send command %s to device %s after retries", command, device_id
        )
        return False
