"""Support for Automation Device Specification (ADS)."""

import asyncio
from collections import namedtuple
import ctypes
from enum import Enum
import logging
import struct
import threading

import pyads
import pyads.errorcodes

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Tuple to hold data needed for notification
NotificationItem = namedtuple(  # noqa: PYI024
    "NotificationItem", "hnotify huser name plc_datatype callback"
)

DEFAULT_TIMEOUT_MS = 5000
OFFLINE_TIMEOUT_MS = 100
WATCHDOG_INTERVAL = 5.0
WATCHDOG_MAX_BACKOFF = 120.0


class ConnectionState(Enum):
    """Representation of the ADS connection state."""

    CONNECTED = 1
    READY_TO_RECONNECT = 2
    DISCONNECTED = 3


class AdsHub:
    """Representation of an ADS connection."""

    def __init__(self, ads_client):
        """Initialize the ADS hub."""
        self._client = ads_client
        self._client.open()
        self._is_running = True

        # All ADS devices are registered here
        self._devices = []
        self._notification_items = {}
        self._lock = threading.Lock()

    def shutdown(self, *args, **kwargs):
        """Shutdown ADS connection."""

        _LOGGER.debug("Shutting down ADS")
        self._is_running = False

        with self._lock:
            for notification_item in self._notification_items.values():
                _LOGGER.debug(
                    "Deleting device notification %d, %d",
                    notification_item.hnotify,
                    notification_item.huser,
                )
                try:
                    self._client.del_device_notification(
                        notification_item.hnotify, notification_item.huser
                    )
                except pyads.ADSError as err:
                    _LOGGER.error(err)
            try:
                self._client.close()
            except pyads.ADSError as err:
                _LOGGER.error(err)

    def register_device(self, device):
        """Register a new device."""
        self._devices.append(device)

    def write_by_name(self, name, value, plc_datatype):
        """Write a value to the device."""

        with self._lock:
            try:
                return self._client.write_by_name(name, value, plc_datatype)
            except pyads.ADSError as err:
                _LOGGER.error("Error writing %s: %s", name, err)

    def read_by_name(self, name, plc_datatype):
        """Read a value from the device."""

        with self._lock:
            try:
                return self._client.read_by_name(name, plc_datatype)
            except pyads.ADSError as err:
                _LOGGER.error("Error reading %s: %s", name, err)

    def add_device_notification(self, name, plc_datatype, callback):
        """Add a notification to the ADS devices."""

        attr = pyads.NotificationAttrib(ctypes.sizeof(plc_datatype))

        with self._lock:
            try:
                hnotify, huser = self._client.add_device_notification(
                    name, attr, self._device_notification_callback
                )
            except pyads.ADSError as err:
                _LOGGER.error("Error subscribing to %s: %s", name, err)
            else:
                hnotify = int(hnotify)
                self._notification_items[hnotify] = NotificationItem(
                    hnotify, huser, name, plc_datatype, callback
                )

                _LOGGER.debug(
                    "Added device notification %d for variable %s", hnotify, name
                )

    async def async_watch_connection(
        self,
        hass: HomeAssistant,
        interval: float = WATCHDOG_INTERVAL,
        max_backoff: float = WATCHDOG_MAX_BACKOFF,
    ) -> None:
        """Watch the connection and restore it after an outage."""
        was_disconnected = False
        wait_time = interval

        while self._is_running:
            try:
                state = await hass.async_add_executor_job(self._check_connection)

                if state is ConnectionState.CONNECTED:
                    if was_disconnected:
                        _LOGGER.info("Reconnected to the ADS device")
                        await hass.async_add_executor_job(self._restore_notifications)
                        was_disconnected = False
                        wait_time = interval

                    await asyncio.sleep(wait_time)
                    continue

                if not was_disconnected:
                    _LOGGER.warning(
                        "Lost connection to the ADS device, waiting for it to return"
                    )
                    was_disconnected = True
                    wait_time = interval
                    await hass.async_add_executor_job(self._suspend_notifications)

                if state is ConnectionState.READY_TO_RECONNECT:
                    await hass.async_add_executor_job(self._reconnect)
                    if self._client.is_open:
                        wait_time = interval

                await asyncio.sleep(wait_time)
                wait_time = min(wait_time * 2, max_backoff)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("Unexpected error while watching the ADS connection")
                await asyncio.sleep(interval)

    def _check_connection(self) -> ConnectionState:
        """Return the current state of the connection."""

        with self._lock:
            if not self._client.is_open:
                return ConnectionState.READY_TO_RECONNECT

            try:
                state = self._client.read_state()
            except pyads.ADSError as err:
                if getattr(err, "err_code", None) not in pyads.errorcodes.ERROR_CODES:
                    return ConnectionState.READY_TO_RECONNECT
                return ConnectionState.DISCONNECTED

            if state is None:
                return ConnectionState.READY_TO_RECONNECT

            return ConnectionState.CONNECTED

    def _reconnect(self) -> None:
        """Reopen the connection to the device."""

        with self._lock:
            try:
                self._client.close()
                self._client.open()
            except pyads.ADSError as err:
                _LOGGER.debug("Reconnect attempt failed: %s", err)

    def _suspend_notifications(self) -> None:
        """Shorten the timeout and drop the notifications the device still holds."""

        self._client.set_timeout(OFFLINE_TIMEOUT_MS)

        with self._lock:
            for notification_item in self._notification_items.values():
                try:
                    self._client.del_device_notification(
                        notification_item.hnotify, notification_item.huser
                    )
                except pyads.ADSError as err:
                    _LOGGER.debug(
                        "Could not delete notification for %s: %s",
                        notification_item.name,
                        err,
                    )

    def _restore_notifications(self) -> None:
        """Restore the timeout and subscribe again to every variable."""

        self._client.set_timeout(DEFAULT_TIMEOUT_MS)

        with self._lock:
            items = list(self._notification_items.values())
            self._notification_items.clear()

        for item in items:
            self.add_device_notification(item.name, item.plc_datatype, item.callback)

    def _device_notification_callback(self, notification, name):
        """Handle device notifications."""
        contents = notification.contents
        hnotify = int(contents.hNotification)
        _LOGGER.debug("Received notification %d", hnotify)

        # Get dynamically sized data array
        data_size = contents.cbSampleSize
        data_address = (
            ctypes.addressof(contents)
            + pyads.structs.SAdsNotificationHeader.data.offset
        )
        data = (ctypes.c_ubyte * data_size).from_address(data_address)

        # Acquire notification item
        with self._lock:
            notification_item = self._notification_items.get(hnotify)

        if not notification_item:
            _LOGGER.error("Unknown device notification handle: %d", hnotify)
            return

        # Data parsing based on PLC data type
        plc_datatype = notification_item.plc_datatype
        unpack_formats = {
            pyads.PLCTYPE_BYTE: "<b",
            pyads.PLCTYPE_INT: "<h",
            pyads.PLCTYPE_UINT: "<H",
            pyads.PLCTYPE_SINT: "<b",
            pyads.PLCTYPE_USINT: "<B",
            pyads.PLCTYPE_DINT: "<i",
            pyads.PLCTYPE_UDINT: "<I",
            pyads.PLCTYPE_WORD: "<H",
            pyads.PLCTYPE_DWORD: "<I",
            pyads.PLCTYPE_LREAL: "<d",
            pyads.PLCTYPE_REAL: "<f",
            pyads.PLCTYPE_TOD: "<i",  # Treat as DINT
            pyads.PLCTYPE_DATE: "<i",  # Treat as DINT
            pyads.PLCTYPE_DT: "<i",  # Treat as DINT
            pyads.PLCTYPE_TIME: "<i",  # Treat as DINT
        }

        if plc_datatype == pyads.PLCTYPE_BOOL:
            value = bool(struct.unpack("<?", bytearray(data))[0])
        elif plc_datatype == pyads.PLCTYPE_STRING:
            value = (
                bytearray(data).split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
            )
        elif plc_datatype in unpack_formats:
            value = struct.unpack(unpack_formats[plc_datatype], bytearray(data))[0]
        else:
            value = bytearray(data)
            _LOGGER.warning("No callback available for this datatype")

        notification_item.callback(notification_item.name, value)
