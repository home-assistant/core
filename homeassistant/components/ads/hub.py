"""Support for Automation Device Specification (ADS)."""

from collections import namedtuple
import ctypes
import logging
import struct
import threading

import pyads

_LOGGER = logging.getLogger(__name__)

# Tuple to hold data needed for notification
NotificationItem = namedtuple(  # noqa: PYI024
    "NotificationItem", "hnotify huser name plc_datatype callback"
)


class AdsHub:
    """Representation of an ADS connection."""

    def __init__(self, ads_client):
        """Initialize the ADS hub."""
        self._client = ads_client
        self._client.open()

        # All ADS devices are registered here
        self._devices = []
        self._notification_items = {}
        self._closed = False
        self._lock = threading.Lock()
        # Held across a notification delete, so shutdown cannot close the
        # client while a dispatcher is still registered. Callbacks never take
        # it, so holding it while a delete waits for them cannot deadlock.
        self._teardown_lock = threading.Lock()

    def shutdown(self, *args, **kwargs):
        """Shutdown ADS connection."""

        _LOGGER.debug("Shutting down ADS")
        with self._teardown_lock:
            with self._lock:
                self._closed = True
                notification_items = list(self._notification_items.values())
            # Deleting a notification waits for its in-flight callbacks, which
            # take self._lock themselves, so this has to run outside it. The
            # items stay registered until then, so those callbacks still find
            # them.
            for notification_item in notification_items:
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
            with self._lock:
                self._notification_items.clear()
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
            # The lock is released again before the client is closed, so I/O
            # started after shutdown began would race the teardown.
            if self._closed:
                _LOGGER.debug("Not writing %s, the hub is shut down", name)
                return None
            try:
                return self._client.write_by_name(name, value, plc_datatype)
            except pyads.ADSError as err:
                _LOGGER.error("Error writing %s: %s", name, err)

    def read_by_name(self, name, plc_datatype):
        """Read a value from the device."""

        with self._lock:
            if self._closed:
                _LOGGER.debug("Not reading %s, the hub is shut down", name)
                return None
            try:
                return self._client.read_by_name(name, plc_datatype)
            except pyads.ADSError as err:
                _LOGGER.error("Error reading %s: %s", name, err)

    def add_device_notification(self, name, plc_datatype, callback) -> int | None:
        """Add a notification to the ADS devices, returning its handle."""

        attr = pyads.NotificationAttrib(ctypes.sizeof(plc_datatype))

        with self._lock:
            if self._closed:
                _LOGGER.debug("Not subscribing to %s, the hub is shut down", name)
                return None
            try:
                handles = self._client.add_device_notification(
                    name, attr, self._device_notification_callback
                )
            except pyads.ADSError as err:
                _LOGGER.error("Error subscribing to %s: %s", name, err)
                return None
            if handles is None:
                # pyads returns None instead of raising when the port is not
                # open. Shutdown is caught above, so this is unexpected.
                _LOGGER.error(
                    "Error subscribing to %s: the connection is not open", name
                )
                return None
            hnotify, huser = handles
            hnotify = int(hnotify)
            self._notification_items[hnotify] = NotificationItem(
                hnotify, huser, name, plc_datatype, callback
            )

            _LOGGER.debug("Added device notification %d for variable %s", hnotify, name)
            return hnotify

    def delete_device_notification(self, hnotify: int) -> None:
        """Delete a single device notification."""

        # The teardown lock keeps shutdown from deleting this one as well.
        with self._teardown_lock:
            with self._lock:
                notification_item = self._notification_items.get(hnotify)
            if notification_item is None:
                # Already gone, most likely torn down by shutdown().
                return
            _LOGGER.debug("Deleting device notification %d", hnotify)
            # Deleting waits for in-flight callbacks, which take self._lock
            # themselves, so this has to run outside it. The item stays
            # registered until then, so those callbacks still find it.
            try:
                self._client.del_device_notification(
                    notification_item.hnotify, notification_item.huser
                )
            except pyads.ADSError as err:
                _LOGGER.error(err)
            # Dropped even when the delete failed: pyads 3.4.0 releases its
            # side of the notification before it raises, so nothing reaches
            # this hub for it any more, and deleting it again at shutdown
            # would raise a KeyError from pyads.
            with self._lock:
                del self._notification_items[hnotify]

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
