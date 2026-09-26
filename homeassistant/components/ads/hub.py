"""Support for Automation Device Specification (ADS)."""

import asyncio
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

# Types not listed here are handled separately or unsupported.
UNPACK_FORMATS = {
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

_original_local_net_id: str | None = None

# set_local_address() rebinds the whole process, so a probe must never overlap a
# hub's I/O; both take this lock. It is reentrant because connecting nests the
# override, the port open and the state read underneath it.
_ads_lock = threading.RLock()


def apply_local_net_id(local_net_id: str | None) -> None:
    """Set a custom local AMS NetID, or restore the original once cleared."""
    global _original_local_net_id  # noqa: PLW0603  # pylint: disable=global-statement
    with _ads_lock:
        if local_net_id is None and _original_local_net_id is None:
            return
        pyads.open_port()
        try:
            # Cache the original NetID so it can be restored once cleared.
            if _original_local_net_id is None:
                _original_local_net_id = pyads.get_local_address().netid
            pyads.set_local_address(local_net_id or _original_local_net_id)
        finally:
            pyads.close_port()


@contextmanager
def local_net_id_probe(local_net_id: str | None) -> Iterator[None]:
    """Temporarily apply a local AMS NetID to probe a connection.

    Restores whichever NetID was active beforehand, so a validation
    attempt never leaves process-wide ADS state changed.
    """
    # The lock is held across the probe so neither another override nor a hub's
    # I/O can run while the candidate identity is active.
    with _ads_lock:
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

        # Cancelled on unload, before the notifications are torn down.
        self.resubscribe_task: asyncio.Task[None] | None = None

        # All ADS devices are registered here
        self._devices: list[AdsEntity] = []
        self._notification_items = {}
        self._closed = False
        # Separate from _ads_lock, which is held across blocking PLC calls, so
        # registering an entity never blocks the event loop.
        self._devices_lock = threading.Lock()

        with _ads_lock:
            self._client.open()

    def shutdown(self):
        """Shutdown ADS connection."""

        _LOGGER.debug("Shutting down ADS")
        with _ads_lock:
            self._closed = True
            notification_items = list(self._notification_items.values())
            self._notification_items.clear()
        # Deleting a notification waits for its in-flight callbacks, which take
        # _ads_lock themselves, so this has to run unlocked.
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
        try:
            self._client.close()
        except pyads.ADSError as err:
            _LOGGER.error(err)

        # Entities cache this hub instance directly and won't pick up a new one.
        for device in self.devices:
            device.mark_unavailable()

    @property
    def devices(self) -> list[AdsEntity]:
        """Return the entities registered with this hub."""
        with self._devices_lock:
            return list(self._devices)

    def register_device(self, device: AdsEntity) -> None:
        """Register a new device."""
        with self._devices_lock:
            self._devices.append(device)

    def unregister_device(self, device: AdsEntity) -> None:
        """Unregister a device."""
        with self._devices_lock:
            self._devices.remove(device)

    def write_by_name(self, name, value, plc_datatype):
        """Write a value to the device."""

        with _ads_lock:
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

        with _ads_lock:
            if self._closed:
                _LOGGER.debug("Not reading %s, the hub is shut down", name)
                return None
            try:
                return self._client.read_by_name(name, plc_datatype)
            except pyads.ADSError as err:
                _LOGGER.error("Error reading %s: %s", name, err)

    def read_state(self):
        """Read the device state, raising if the device does not answer."""

        with _ads_lock:
            return self._client.read_state()

    def add_device_notification(self, name, plc_datatype, notification_callback):
        """Add a notification to the ADS devices, returning its handle."""

        attr = pyads.NotificationAttrib(ctypes.sizeof(plc_datatype))

        with _ads_lock:
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
                # pyads returns None instead of raising once the port is closed.
                _LOGGER.debug("Not subscribing to %s, the connection is closed", name)
                return None
            hnotify, huser = handles
            hnotify = int(hnotify)
            self._notification_items[hnotify] = NotificationItem(
                hnotify, huser, name, plc_datatype, notification_callback
            )

            _LOGGER.debug("Added device notification %d for variable %s", hnotify, name)
            return hnotify

    def delete_device_notification(self, hnotify: int) -> None:
        """Delete a single device notification."""

        with _ads_lock:
            notification_item = self._notification_items.pop(hnotify, None)
        if notification_item is None:
            # Already gone, most likely torn down by shutdown().
            return
        _LOGGER.debug("Deleting device notification %d", hnotify)
        # Deleting waits for in-flight callbacks, which take _ads_lock
        # themselves, so this has to run unlocked.
        try:
            self._client.del_device_notification(
                notification_item.hnotify, notification_item.huser
            )
        except pyads.ADSError as err:
            _LOGGER.error(err)

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
        with _ads_lock:
            notification_item = self._notification_items.get(hnotify)

        if not notification_item:
            _LOGGER.error("Unknown device notification handle: %d", hnotify)
            return

        plc_datatype = notification_item.plc_datatype
        if plc_datatype == pyads.PLCTYPE_BOOL:
            value = bool(struct.unpack("<?", bytearray(data))[0])
        elif plc_datatype == pyads.PLCTYPE_STRING:
            value = (
                bytearray(data).split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
            )
        elif plc_datatype in UNPACK_FORMATS:
            value = struct.unpack(UNPACK_FORMATS[plc_datatype], bytearray(data))[0]
        else:
            value = bytearray(data)
            _LOGGER.warning("No callback available for this datatype")

        notification_item.callback(notification_item.name, value)


def connect(
    device: str, port: int, ip_address: str | None, local_net_id: str | None
) -> AdsHub:
    """Connect to the ADS device and verify it responds."""
    # Held across the whole handshake so a config flow probe cannot swap the
    # local AMS NetID out from under the port open or the state read.
    with _ads_lock:
        apply_local_net_id(local_net_id)
        hub: AdsHub | None = None
        try:
            hub = AdsHub(pyads.Connection(device, port, ip_address))
            hub.read_state()
        except pyads.ADSError, RuntimeError:
            if hub is not None:
                # No notification is subscribed yet, so this cannot wait on a
                # callback.
                hub.shutdown()
            if local_net_id:
                # A failed entry is never unloaded, so the process-wide override
                # has to be undone here or it outlives the failed connection.
                apply_local_net_id(None)
            raise
        return hub


type AdsConfigEntry = ConfigEntry[AdsHub]


@callback
def async_get_hub(hass: HomeAssistant) -> AdsHub:
    """Return the hub of the loaded ADS config entry."""
    entries: list[AdsConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise PlatformNotReady("ADS connection is not set up")
    return entries[0].runtime_data
