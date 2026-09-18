"""Support for Automation Device Specification (ADS)."""

from collections import namedtuple
from collections.abc import Iterator
from contextlib import contextmanager
import ctypes
import logging
import struct
import threading
from typing import TYPE_CHECKING

import pyads

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady

from .const import DOMAIN

if TYPE_CHECKING:
    from .entity import AdsEntity

_LOGGER = logging.getLogger(__name__)

# Tuple to hold data needed for notification
NotificationItem = namedtuple(  # noqa: PYI024
    "NotificationItem", "hnotify huser name plc_datatype callback"
)

_original_local_net_id: str | None = None


def apply_local_net_id(local_net_id: str | None) -> None:
    """Set a custom local AMS NetID, or restore the original once cleared."""
    global _original_local_net_id  # noqa: PLW0603  # pylint: disable=global-statement
    if local_net_id is None and _original_local_net_id is None:
        return
    pyads.open_port()
    try:
        # set_local_address() is process-wide; cache the original to restore it.
        if _original_local_net_id is None:
            _original_local_net_id = pyads.get_local_address().netid
        pyads.set_local_address(local_net_id or _original_local_net_id)
    finally:
        pyads.close_port()


def _reset_local_net_id_cache() -> None:
    """Reset the cached original local AMS NetID.

    Only meant for test isolation between config entries.
    """
    global _original_local_net_id  # noqa: PLW0603  # pylint: disable=global-statement
    _original_local_net_id = None


@contextmanager
def local_net_id_probe(local_net_id: str | None) -> Iterator[None]:
    """Temporarily apply a local AMS NetID to probe a connection.

    Restores whichever NetID was active beforehand, so a validation
    attempt never leaves process-wide ADS state changed.
    """
    target_net_id = local_net_id or _original_local_net_id
    if target_net_id is None:
        yield
        return
    pyads.open_port()
    try:
        previous_net_id = pyads.get_local_address().netid
        pyads.set_local_address(target_net_id)
    finally:
        pyads.close_port()
    try:
        yield
    finally:
        pyads.open_port()
        try:
            pyads.set_local_address(previous_net_id)
        finally:
            pyads.close_port()


class AdsHub:
    """Representation of an ADS connection."""

    def __init__(self, ads_client):
        """Initialize the ADS hub."""
        self._client = ads_client
        self._client.open()

        # All ADS devices are registered here
        self._devices: list[AdsEntity] = []
        self._notification_items = {}
        self._lock = threading.Lock()

    def shutdown(self):
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
        self._notification_items.clear()
        try:
            self._client.close()
        except pyads.ADSError as err:
            _LOGGER.error(err)

        # Entities cache this hub instance directly and won't pick up a new one.
        for device in self._devices:
            device.mark_unavailable()

    @property
    def devices(self) -> list[AdsEntity]:
        """Return the entities registered with this hub."""
        return self._devices

    def register_device(self, device: AdsEntity) -> None:
        """Register a new device."""
        self._devices.append(device)

    def unregister_device(self, device: AdsEntity) -> None:
        """Unregister a device."""
        self._devices.remove(device)

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

    def add_device_notification(self, name, plc_datatype, notification_callback):
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
                    hnotify, huser, name, plc_datatype, notification_callback
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


type AdsConfigEntry = ConfigEntry[AdsHub]


@callback
def async_get_hub(hass: HomeAssistant) -> AdsHub:
    """Return the hub of the loaded ADS config entry."""
    entries: list[AdsConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise PlatformNotReady("ADS connection is not set up")
    return entries[0].runtime_data
