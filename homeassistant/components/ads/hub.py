"""Support for Automation Device Specification (ADS)."""

from collections import namedtuple
import concurrent.futures
import ctypes
import logging
import struct
import threading
import uuid

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
        self._mac_address = self.get_mac_address()
        self._devices = []
        self._notification_items = {}
        self._lock = threading.Lock()

    def get_mac_address(self):
        """Retrieve the MAC address of the device."""
        try:
            mac = uuid.getnode()
            mac_address = ":".join(
                format((mac >> 8 * i) & 0xFF, "02x") for i in range(6)[::-1]
            ).upper()
            _LOGGER.info("Successfully retrieved MAC address: %s", mac_address)
        except (OSError, ValueError) as err:
            _LOGGER.error("Failed to retrieve MAC address: %s", err)
            return None
        else:
            return mac_address

    def test_connection(self, timeout=5):
        """Test the ADS connection by opening and closing the client connection with a timeout."""
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._try_open_and_check_connection)
                return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            _LOGGER.error(
                "Connection test timed out. IP address may be invalid or unreachable"
            )
            return False

    def _try_open_and_check_connection(self):
        """Try opening the connection and performing a simple check."""
        try:
            self._client.open()
            if self._client.is_open:
                # Perform a simple check (e.g., read state) to confirm the AMS Net ID is valid
                try:
                    self._client.read_state()
                    return True  # noqa: TRY300
                except pyads.ADSError as err:
                    _LOGGER.error("AMS Net ID validation failed: %s", err)
                finally:
                    self._client.close()
            return False  # noqa: TRY300
        except pyads.ADSError as err:
            _LOGGER.error("Connection attempt failed: %s", err)
            return False

    def shutdown(self, *args, **kwargs):
        """Shutdown ADS connection."""

        _LOGGER.debug("Shutting down ADS")
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
