"""Support for Automation Device Specification (ADS)."""

import asyncio
from collections import namedtuple
from contextlib import suppress
import ctypes
import logging
import socket
import struct
import threading
from typing import TYPE_CHECKING

import pyads

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady

from .const import DATA_SETUP_DONE, DOMAIN

if TYPE_CHECKING:
    from .entity import AdsEntity

_LOGGER = logging.getLogger(__name__)

# The AMS router talks to the device over this TCP port.
ADS_TCP_PORT = 48898
# How long to wait for the device to accept a TCP connection.
REACHABLE_TIMEOUT = 5
# How long a YAML platform waits for the entry's setup attempt to finish.
HUB_WAIT_TIMEOUT = 30

# Tuple to hold data needed for notification
NotificationItem = namedtuple(  # noqa: PYI024
    "NotificationItem", "hnotify huser name plc_datatype callback"
)


class AdsHub:
    """Representation of an ADS connection."""

    def __init__(self, ads_client) -> None:
        """Initialize the ADS hub."""
        self._client = ads_client
        self._client.open()

        # Cancelled on unload, before the notifications are torn down.
        self.resubscribe_task: asyncio.Task[None] | None = None

        # All ADS devices are registered here
        self._devices: list[AdsEntity] = []
        # Separate from the I/O locks, so registering an entity never waits on
        # a blocking PLC call from the event loop.
        self._devices_lock = threading.Lock()
        self._notification_items: dict[int, NotificationItem] = {}
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

        # Entities hold this hub directly and stop hearing from the PLC now.
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

    def read_state(self) -> tuple[int, int]:
        """Read the device state, raising if the device does not answer."""
        with self._lock:
            state = self._client.read_state()
        if state is None:
            # pyads returns None instead of raising when the port is closed.
            raise pyads.ADSError(err_code=1864)
        return state

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

    def add_device_notification(
        self, name, plc_datatype, notification_callback
    ) -> int | None:
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
                hnotify, huser, name, plc_datatype, notification_callback
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


def check_reachable(device: str, ip_address: str | None) -> None:
    """Raise OSError unless the device accepts a TCP connection on the ADS port.

    The AMS router keeps retrying the connection to a device that does not
    answer, about 75 seconds per attempt, so the first request through pyads
    would block for minutes instead of failing.
    """
    # pyads derives the address from the AMS NetID the same way.
    host = ip_address or ".".join(device.split(".")[:4])
    with socket.create_connection((host, ADS_TCP_PORT), timeout=REACHABLE_TIMEOUT):
        pass


def connect(device: str, port: int, ip_address: str | None) -> AdsHub:
    """Connect to the ADS device and verify it responds.

    Raises OSError when the device does not answer at all, and RuntimeError
    when the AMS router refuses to open a port.
    """
    check_reachable(device, ip_address)
    hub = AdsHub(pyads.Connection(device, port, ip_address))
    try:
        hub.read_state()
    except pyads.ADSError:
        # Nothing is subscribed yet, so this cannot wait on a callback.
        hub.shutdown()
        raise
    return hub


type AdsConfigEntry = ConfigEntry[AdsHub]


async def async_wait_for_hub(hass: HomeAssistant) -> AdsHub:
    """Return the hub once the entry's setup attempt finished.

    YAML platforms are set up while the entry imported from YAML is still being
    created and connected; failing at once would leave them retrying on a
    timer of their own long after the connection is up.
    """
    with suppress(TimeoutError):
        async with asyncio.timeout(HUB_WAIT_TIMEOUT):
            await hass.data[DATA_SETUP_DONE].wait()
    return async_get_hub(hass)


@callback
def async_get_hub(hass: HomeAssistant) -> AdsHub:
    """Return the hub of the loaded ADS config entry."""
    entries: list[AdsConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise PlatformNotReady("The ADS connection is not set up")
    return entries[0].runtime_data
