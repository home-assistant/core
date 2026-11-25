"""Support for Automation Device Specification (ADS)."""

import asyncio
from collections.abc import Callable
from contextlib import suppress
import ctypes
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from functools import partial
from itertools import count
import logging
import socket
import struct
import threading
from typing import TYPE_CHECKING, Any

import pyads

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers.event import async_call_later, async_track_time_interval

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

# A lost connection is noticed at most this long after it happened.
PROBE_INTERVAL = timedelta(seconds=30)

# A PLC being restarted or redeployed is gone for minutes, so back off instead
# of asking the same question every few seconds.
RECONNECT_MIN_INTERVAL = 5.0
RECONNECT_MAX_INTERVAL = 300.0

# Milliseconds. A device that stopped answering will not answer the deletions
# of its notifications either, and the full timeout on each of a few hundred of
# them would take the teardown into the minutes.
ADS_TIMEOUT = 5000
TEARDOWN_TIMEOUT = 100

# ADS errors meaning the device stopped answering, as opposed to refusing one
# variable, for example after a download removed it.
CONNECTION_ERRORS = frozenset({13, 21, 27, 1861, 1864})


@dataclass
class Subscription:
    """A variable an entity subscribed to, kept across reconnects.

    The ADS device issues the notification handle, so it changes on every
    reconnect; everything needed to ask for a new one stays here.
    """

    name: str
    plc_datatype: type
    callback: Callable[[str, Any], None]
    handles: tuple[int, int] | None = None


class ConnectionState(StrEnum):
    """What the hub knows about the ADS device."""

    RUNNING = "running"
    # Answering, but the PLC is not in RUN. The subscriptions are kept, since
    # they come back on their own once the PLC runs again.
    STOPPED = "stopped"
    # Not answering. The connection is torn down and rebuilt.
    LOST = "lost"


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


class AdsHub:
    """Representation of an ADS connection."""

    def __init__(
        self, ads_client, device: str = "", ip_address: str | None = None
    ) -> None:
        """Initialize the ADS hub."""
        self._client = ads_client
        self._client.open()
        self._device = device
        self._ip_address = ip_address

        # Cancelled on unload, before the notifications are torn down.
        self.resubscribe_task: asyncio.Task[None] | None = None

        # All ADS devices are registered here
        self._devices: list[AdsEntity] = []
        # Separate from the I/O locks, so registering an entity never waits on
        # a blocking PLC call from the event loop.
        self._devices_lock = threading.Lock()
        self._subscriptions: dict[int, Subscription] = {}
        self._subscription_ids = count(1)
        self._subscription_ids_by_hnotify: dict[int, int] = {}
        self._state = ConnectionState.RUNNING
        # Whether the client's port is open. Written under self._lock by the
        # threads that open and close it, unlike self._state, which the event
        # loop owns.
        self._port_open = True
        self._closed = False
        self._lock = threading.Lock()
        # Held across a notification delete, so shutdown cannot close the
        # client while a dispatcher is still registered. Callbacks never take
        # it, so holding it while a delete waits for them cannot deadlock.
        self._teardown_lock = threading.Lock()

        self._hass: HomeAssistant | None = None
        self._cancel_probe: CALLBACK_TYPE | None = None
        self._cancel_reconnect: CALLBACK_TYPE | None = None
        self._probing = False
        self._monitoring = False

    @property
    def connected(self) -> bool:
        """Return whether the device answers and its PLC is running."""
        return not self._closed and self._state is ConnectionState.RUNNING

    @callback
    def async_start_monitoring(self, hass: HomeAssistant) -> None:
        """Probe the device from now on, and rebuild the connection once lost.

        The ADS device never announces that it went away, and a connection it
        dropped stays open on this side, so it has to be probed.
        """
        self._hass = hass
        self._monitoring = True
        self._cancel_probe = async_track_time_interval(
            hass, self._async_probe, PROBE_INTERVAL
        )

    @callback
    def async_stop_monitoring(self) -> None:
        """Stop probing and reconnecting.

        A probe or reconnect already running finishes, but schedules nothing.
        """
        self._monitoring = False
        if self._cancel_probe is not None:
            self._cancel_probe()
            self._cancel_probe = None
        if self._cancel_reconnect is not None:
            self._cancel_reconnect()
            self._cancel_reconnect = None

    async def _async_probe(self, now: datetime) -> None:
        """Check the device still answers and runs."""
        assert self._hass is not None
        if self._probing or self._state is ConnectionState.LOST or self._closed:
            return
        self._probing = True
        try:
            ads_state, error = await self._hass.async_add_executor_job(
                self._probe_state
            )
        finally:
            self._probing = False
        if not self._monitoring:
            return
        if ads_state is None:
            _LOGGER.info("Lost the connection to the ADS device: %s", error)
            # Set before the teardown, which can outlast the probe interval
            # with a few hundred notifications; a probe still seeing RUNNING
            # would drop the connection a second time.
            self._async_set_state(ConnectionState.LOST)
            await self._hass.async_add_executor_job(self._drop_connection)
            # The deletions waited for the last callbacks, so no value from the
            # lost connection arrives after this. A variable that cannot be
            # subscribed again stays unavailable instead of showing it.
            for device in self.devices:
                device.mark_unavailable()
            self._async_schedule_reconnect(RECONNECT_MIN_INTERVAL)
        elif ads_state == pyads.ADSSTATE_RUN:
            if self._state is ConnectionState.STOPPED:
                _LOGGER.info("The ADS device is running again")
                self._async_set_state(ConnectionState.RUNNING)
        elif self._state is ConnectionState.RUNNING:
            _LOGGER.info("The ADS device stopped running (ADS state %s)", ads_state)
            self._async_set_state(ConnectionState.STOPPED)

    def _probe_state(self) -> tuple[int | None, str | None]:
        """Read the ADS state, returning it or why the device did not answer."""
        with self._lock:
            if self._closed:
                return None, "the hub is shut down"
            try:
                state = self._client.read_state()
            except pyads.ADSError as err:
                return None, str(err)
        if state is None:
            # pyads returns None instead of raising when the port is closed.
            return None, str(pyads.ADSError(err_code=1864))
        return state[0], None

    @callback
    def _async_set_state(self, state: ConnectionState) -> None:
        """Remember what the device is doing and update the entities."""
        self._state = state
        for device in self.devices:
            device.async_connection_changed()

    def _drop_connection(self) -> None:
        """Release the notifications, then close the connection.

        The notifications have to go first: the ADS library drops its
        dispatcher for one whether or not the device answers the deletion, and
        closing a connection whose dispatchers are still live takes the whole
        process down with it. The device will not answer, so each deletion
        only waits briefly.
        """
        with self._teardown_lock:
            with self._lock:
                # Nothing registers on the port from here on.
                self._port_open = False
                handles = [
                    subscription.handles
                    for subscription in self._subscriptions.values()
                    if subscription.handles is not None
                ]
                for subscription in self._subscriptions.values():
                    subscription.handles = None
                self._subscription_ids_by_hnotify.clear()
                self._client.set_timeout(TEARDOWN_TIMEOUT)
            # Deleting waits for in-flight callbacks, which take self._lock
            # themselves, so this has to run outside it.
            for hnotify, huser in handles:
                try:
                    self._client.del_device_notification(hnotify, huser)
                except pyads.ADSError as err:
                    _LOGGER.debug(
                        "Deleting device notification %d failed: %s", hnotify, err
                    )
            try:
                self._client.close()
            except pyads.ADSError as err:
                _LOGGER.debug("Closing the ADS connection failed: %s", err)

    @callback
    def _async_schedule_reconnect(self, delay: float) -> None:
        """Try again after a delay that grows while the device stays away."""
        assert self._hass is not None
        if not self._monitoring:
            return
        self._cancel_reconnect = async_call_later(
            self._hass, delay, partial(self._async_reconnect, delay)
        )

    async def _async_reconnect(self, delay: float, now: datetime) -> None:
        """Rebuild the connection and the subscriptions once the device answers."""
        assert self._hass is not None
        self._cancel_reconnect = None
        if not self._monitoring:
            return
        ads_state = await self._hass.async_add_executor_job(self._reconnect)
        if not self._monitoring:
            return
        if ads_state is None:
            self._async_schedule_reconnect(min(delay * 2, RECONNECT_MAX_INTERVAL))
            return
        if ads_state == pyads.ADSSTATE_RUN:
            _LOGGER.info("Reconnected to the ADS device")
            self._async_set_state(ConnectionState.RUNNING)
        else:
            _LOGGER.info(
                "Reconnected to the ADS device, which is not running (ADS state %s)",
                ads_state,
            )
            self._async_set_state(ConnectionState.STOPPED)

    def _reconnect(self) -> int | None:
        """Reopen the connection and resubscribe, returning the ADS state."""
        try:
            # Without this, the AMS router keeps retrying the TCP connection to
            # a device that is still away, about 75 seconds per attempt.
            check_reachable(self._device, self._ip_address)
        except OSError as err:
            _LOGGER.debug("The ADS device is still unreachable: %s", err)
            return None
        with self._lock:
            if self._closed:
                return None
            try:
                self._client.open()
                self._client.set_timeout(ADS_TIMEOUT)
                state = self._client.read_state()
            except (pyads.ADSError, RuntimeError) as err:
                _LOGGER.debug("Reopening the ADS connection failed: %s", err)
                state = None
            if state is None:
                with suppress(pyads.ADSError):
                    self._client.close()
                return None
            self._port_open = True
            subscription_ids = list(self._subscriptions)
        for subscription_id in subscription_ids:
            if not self._register(subscription_id):
                # Gone again, so the rest would each wait the full timeout.
                _LOGGER.debug("The ADS device stopped answering while resubscribing")
                self._drop_connection()
                return None
        return state[0]

    def shutdown(self, *args, **kwargs):
        """Shutdown ADS connection."""

        _LOGGER.debug("Shutting down ADS")
        with self._teardown_lock:
            with self._lock:
                self._closed = True
                port_open = self._port_open
                self._port_open = False
                handles = [
                    subscription.handles
                    for subscription in self._subscriptions.values()
                    if subscription.handles is not None
                ]
                if port_open:
                    # A device that went away unnoticed would make each
                    # deletion wait the full timeout.
                    self._client.set_timeout(TEARDOWN_TIMEOUT)
            # Deleting a notification waits for its in-flight callbacks, which
            # take self._lock themselves, so this has to run outside it. The
            # subscriptions stay registered until then, so those callbacks
            # still find them.
            for hnotify, huser in handles:
                _LOGGER.debug("Deleting device notification %d, %d", hnotify, huser)
                try:
                    self._client.del_device_notification(hnotify, huser)
                except pyads.ADSError as err:
                    _LOGGER.error(err)
            with self._lock:
                self._subscriptions.clear()
                self._subscription_ids_by_hnotify.clear()
            if port_open:
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
        """Write a value to the device.

        Raises HomeAssistantError while the connection is lost, since pyads
        would silently drop a write to the closed port.
        """

        with self._lock:
            # The lock is released again before the client is closed, so I/O
            # started after shutdown began would race the teardown.
            if self._closed:
                _LOGGER.debug("Not writing %s, the hub is shut down", name)
                return None
            if not self._port_open:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="not_connected",
                    translation_placeholders={"variable": name},
                )
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
        """Subscribe to a variable, returning an id to unsubscribe it by.

        The id stays valid across reconnects, unlike the notification handle.
        A subscription the device refuses is kept and asked for again on the
        next reconnect, so a variable that appears after a download is picked
        up. Returns None once the hub is shut down.
        """
        with self._lock:
            if self._closed:
                _LOGGER.debug("Not subscribing to %s, the hub is shut down", name)
                return None
            subscription_id = next(self._subscription_ids)
            self._subscriptions[subscription_id] = Subscription(
                name, plc_datatype, notification_callback
            )
        self._register(subscription_id)
        return subscription_id

    def is_registered(self, subscription_id: int) -> bool:
        """Return whether the device currently notifies on a subscription."""
        with self._lock:
            subscription = self._subscriptions.get(subscription_id)
            return subscription is not None and subscription.handles is not None

    def _register(self, subscription_id: int) -> bool:
        """Ask the device to notify on a subscription's variable.

        Returns False when the device did not answer, and True otherwise, also
        when it refused the variable.

        While the connection is lost this waits for the reconnect, which
        registers every subscription again. The teardown lock keeps a delete,
        a drop or shutdown from running between the check and the
        registration, which would leave a notification nobody deletes.
        """
        with self._teardown_lock:
            return self._register_locked(subscription_id)

    def _register_locked(self, subscription_id: int) -> bool:
        """Register a subscription; the caller holds the teardown lock."""
        with self._lock:
            subscription = self._subscriptions.get(subscription_id)
            if subscription is None or self._closed or not self._port_open:
                return True
            if subscription.handles is not None:
                # Added just before a reconnect took its snapshot, so both
                # register it; a second registration would orphan the first.
                return True
            attr = pyads.NotificationAttrib(ctypes.sizeof(subscription.plc_datatype))
            try:
                handles = self._client.add_device_notification(
                    subscription.name, attr, self._device_notification_callback
                )
            except pyads.ADSError as err:
                _LOGGER.error("Error subscribing to %s: %s", subscription.name, err)
                return getattr(err, "err_code", None) not in CONNECTION_ERRORS
            if handles is None:
                # pyads returns None instead of raising when the port is not
                # open.
                _LOGGER.error(
                    "Error subscribing to %s: the connection is not open",
                    subscription.name,
                )
                return False
            hnotify, huser = int(handles[0]), int(handles[1])
            subscription.handles = (hnotify, huser)
            self._subscription_ids_by_hnotify[hnotify] = subscription_id
            _LOGGER.debug(
                "Added device notification %d for variable %s",
                hnotify,
                subscription.name,
            )
            return True

    def delete_device_notification(self, subscription_id: int) -> None:
        """Unsubscribe, deleting the device notification if there is one."""

        # The teardown lock keeps shutdown from deleting this one as well.
        with self._teardown_lock:
            with self._lock:
                subscription = self._subscriptions.get(subscription_id)
            if subscription is None:
                # Already gone, most likely torn down by shutdown().
                return
            if (handles := subscription.handles) is not None:
                _LOGGER.debug("Deleting device notification %d", handles[0])
                # Deleting waits for in-flight callbacks, which take self._lock
                # themselves, so this has to run outside it. The subscription
                # stays registered until then, so those callbacks still find it.
                try:
                    self._client.del_device_notification(*handles)
                except pyads.ADSError as err:
                    _LOGGER.error(err)
            # Dropped even when the delete failed: pyads 3.4.0 releases its
            # side of the notification before it raises, so nothing reaches
            # this hub for it any more, and deleting it again at shutdown
            # would raise a KeyError from pyads.
            with self._lock:
                del self._subscriptions[subscription_id]
                if handles is not None:
                    self._subscription_ids_by_hnotify.pop(handles[0], None)

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

        # Acquire the subscription
        with self._lock:
            subscription_id = self._subscription_ids_by_hnotify.get(hnotify)
            subscription = (
                None
                if subscription_id is None
                else self._subscriptions.get(subscription_id)
            )

        if not subscription:
            # Expected for a notification still in flight when its
            # subscription was deleted or the connection dropped.
            _LOGGER.debug("Unknown device notification handle: %d", hnotify)
            return

        # Data parsing based on PLC data type
        plc_datatype = subscription.plc_datatype

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

        subscription.callback(subscription.name, value)


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
    hub = AdsHub(pyads.Connection(device, port, ip_address), device, ip_address)
    try:
        ads_state, _ = hub.read_state()
    except pyads.ADSError:
        # Nothing is subscribed yet, so this cannot wait on a callback.
        hub.shutdown()
        raise
    if ads_state != pyads.ADSSTATE_RUN:
        # Nothing listens to the hub yet, so no entity needs updating.
        hub._state = ConnectionState.STOPPED  # noqa: SLF001
    return hub


type AdsConfigEntry = ConfigEntry[AdsHub]


async def async_wait_for_hub(hass: HomeAssistant) -> AdsHub:
    """Return the hub once the entry's setup attempt finished.

    YAML platforms are set up while the entry imported from YAML is still being
    created and connected, so they wait for that attempt instead of failing at
    once and retrying on a timer of their own. When the attempt does not load
    the entry, they still raise PlatformNotReady and retry on their timer.
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
