"""Manage a Gree device connection for each config entry."""

import asyncio
import copy
from datetime import datetime, timedelta
import logging
from typing import Any, override

from greeclimate.device import Device, DeviceInfo
from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError
from greeclimate.network import Response

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .const import (
    CONF_IDENTIFIER,
    DOMAIN,
    MAX_ERRORS,
    MAX_EXPECTED_RESPONSE_TIME_INTERVAL,
    UPDATE_INTERVAL,
)
from .discovery import async_get_discovery

_LOGGER = logging.getLogger(__name__)

type GreeConfigEntry = ConfigEntry[DeviceDataUpdateCoordinator]


async def async_bind_device(hass: HomeAssistant, device: Device) -> None:
    """Open the scan-gated firmware window before binding the saved device."""
    await async_get_discovery(hass).async_scan(wait_for=0)
    await device.bind()


class DeviceDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll one device without replacing its connection under entity actions."""

    config_entry: GreeConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: GreeConfigEntry) -> None:
        """Initialize the coordinator from the saved device endpoint."""
        data = config_entry.data
        self.device = Device(
            DeviceInfo(
                ip=data[CONF_HOST],
                port=data[CONF_PORT],
                mac=data[CONF_IDENTIFIER],
                name=data[CONF_NAME],
                brand=data["brand"],
                model=data["model"],
                version=data["version"],
                mid=data["mid"],
            )
        )
        self._error_count = 0
        self._last_response_time: datetime = utcnow()
        self._last_error_time: datetime | None = None
        self._device_task: asyncio.Task | None = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-{self.device.device_info.name}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            always_update=False,
        )
        self.device.add_handler(Response.RESULT, self.device_state_updated)
        self._unsub_shutdown = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._async_hass_stop
        )

    async def _async_hass_stop(self, event: Event) -> None:
        """Retire the connection when Home Assistant stops."""
        self._unsub_shutdown = None
        await self.async_shutdown()

    @callback
    def device_state_updated(self, *args: Any) -> None:
        """Handle device state updates."""
        if self._shutdown_requested:
            return
        _LOGGER.debug("Device state updated: %s", json_dumps(args))
        self._error_count = 0
        self._last_response_time = utcnow()
        self.async_set_updated_data(self.device.raw_properties)

    @override
    async def _async_setup(self) -> None:
        """Bind the fixed device before the first status request."""
        self._device_task = asyncio.current_task()
        try:
            await async_bind_device(self.hass, self.device)
        except (
            DeviceNotBoundError,
            DeviceTimeoutError,
            OSError,
            TimeoutError,
        ) as error:
            await self.async_shutdown()
            raise UpdateFailed(
                f"Unable to bind to {self.device.device_info}"
            ) from error
        except BaseException:
            await self.async_shutdown()
            raise
        else:
            if self._shutdown_requested:
                raise asyncio.CancelledError
        finally:
            self._device_task = None

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update the state of the device."""
        _LOGGER.debug(
            "Updating device state: %s, error count: %d", self.name, self._error_count
        )
        self._device_task = asyncio.current_task()
        try:
            try:
                await self.device.update_state()
            except DeviceNotBoundError as error:
                raise UpdateFailed(
                    f"Device {self.name} is unavailable, device is not bound."
                ) from error
            except DeviceTimeoutError as error:
                self._error_count += 1

                # Under normal conditions GREE units timeout every once in a while
                if self.last_update_success and self._error_count >= MAX_ERRORS:
                    raise UpdateFailed(
                        f"Device {self.name} at {self.device.device_info.ip} is"
                        " unavailable, could not send update request"
                    ) from error
            else:
                # raise update failed if time for more than
                # MAX_ERRORS has passed since last update
                now = utcnow()
                elapsed_success = now - self._last_response_time
                if self.update_interval and elapsed_success >= timedelta(
                    seconds=MAX_EXPECTED_RESPONSE_TIME_INTERVAL
                ):
                    if not self._last_error_time or (
                        (now - self.update_interval) >= self._last_error_time
                    ):
                        self._last_error_time = now
                        self._error_count += 1

                    _LOGGER.warning(
                        "Device %s took an unusually long time to respond, %s seconds",
                        self.name,
                        elapsed_success,
                    )
                else:
                    self._error_count = 0
                if self.last_update_success and self._error_count >= MAX_ERRORS:
                    raise UpdateFailed(
                        f"Device {self.name} is unresponsive for"
                        " too long and now unavailable"
                    )

            self._last_response_time = utcnow()
            return copy.deepcopy(self.device.raw_properties)
        finally:
            self._device_task = None

    @override
    async def async_shutdown(self) -> None:
        """Retire the device and cancel work without reopening its session."""
        if self._shutdown_requested:
            return
        await super().async_shutdown()
        if (
            self._device_task is not None
            and self._device_task is not asyncio.current_task()
        ):
            self._device_task.cancel()
        self.device.close()

    async def push_state_update(self):
        """Send state updates to the physical device."""
        try:
            return await self.device.push_state_update()
        except DeviceTimeoutError:
            _LOGGER.warning(
                "Timeout send state update to: %s (%s)",
                self.name,
                self.device.device_info,
            )
