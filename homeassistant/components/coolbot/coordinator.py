"""Keeps a live connection to the CoolBot cloud and publishes state to entities."""

import asyncio
from datetime import datetime
import logging
from typing import override

from pycoolbot import CoolbotAuthError, CoolbotClient, CoolbotDevice, CoolbotError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONNECT_TIMEOUT_SECONDS,
    DOMAIN,
    MAINTENANCE_INTERVAL,
    PROFILE_REFRESH_INTERVAL,
    STALE_AFTER_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

type CoolbotConfigEntry = ConfigEntry[CoolbotCoordinator]


class CoolbotCoordinator(DataUpdateCoordinator[dict[str, CoolbotDevice]]):
    """Maintains one socket to the CoolBot cloud for a config entry.

    The service pushes, so this has no update interval: the client calls back as
    each reading lands and the new state is published there and then.

    A timer still runs, but not to fetch anything. It keeps the socket alive and
    notices when it has died, and it re-examines staleness, which is a function
    of time rather than of any message: a cooler that stops reporting sends
    nothing to say so, and its entities have to go unavailable regardless.

    Reconnection is handled here rather than in the library: a CoolBot drops off
    and returns every few minutes, and the socket does not always survive that.
    """

    config_entry: CoolbotConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CoolbotConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry)
        self._client: CoolbotClient | None = None
        #: Removes the client callback; held so a replaced client does not leave
        #: a listener behind that publishes from a socket no longer in use.
        self._remove_listener: CALLBACK_TYPE | None = None
        self._cancel_maintenance: CALLBACK_TYPE | None = None
        #: Cleared when the stop event fires, since removing a one-time
        #: listener that has already run logs an error.
        self._unsub_stop: CALLBACK_TYPE | None = None
        #: The pass in flight, held so teardown can stop it: a pass that is
        #: reconnecting would otherwise install a client after teardown closed
        #: the last one, and nothing would ever close it.
        self._maintenance_task: asyncio.Task[None] | None = None
        #: Held across a reconnect: maintenance and an explicit refresh can both
        #: find the socket down, and two connects would orphan whichever client
        #: the other replaced, socket and listener alike.
        self._connect_lock = asyncio.Lock()
        #: Set by teardown, so a connect still in flight closes its own client
        #: instead of handing over a socket that nothing will close.
        self._closed = False
        #: Name and hardware details last written to the device registry, per
        #: unique id, so an unchanged refresh does not touch the registry at all.
        self._device_details: dict[str, tuple[str, str, str | None, str | None]] = {}
        #: When the account profile was last read, connecting included.
        self._profile_read_at: datetime | None = None

    @override
    async def _async_setup(self) -> None:
        """Connect and start the timer, before the initial refresh."""
        try:
            await self._async_connect()
        except CoolbotAuthError as err:
            raise self._auth_error(err) from err
        except CoolbotError as err:
            raise self._connection_error(err) from err

        self._cancel_maintenance = async_track_time_interval(
            self.hass, self._schedule_maintenance, MAINTENANCE_INTERVAL
        )
        # Registered on the entry, not left to unload alone: a first refresh
        # that fails never assigns runtime_data, so the unload path cannot
        # reach this coordinator, and the timer and socket would outlive the
        # attempt. Home Assistant runs these when a setup fails too.
        self.config_entry.async_on_unload(self._async_teardown)
        # Entries are not unloaded when Home Assistant stops, so without this
        # the timer would go on starting passes and a reconnect would hold up
        # the stop until the shared session closed underneath it.
        self._unsub_stop = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._async_on_stop
        )

    async def _async_on_stop(self, _event: Event) -> None:
        self._unsub_stop = None
        await self._async_teardown()

    async def _async_connect(self) -> None:
        """Open a socket and listen to it.

        Raises the library's own errors; callers decide what each one means,
        because the same failure aborts setup in one place and only marks the
        entities unavailable in another.
        """
        if self._closed:
            # Teardown cancels the pass that got here, but closing the old
            # client awaits the library's reader and can swallow that
            # cancellation; connecting anyway would hold up the unload.
            raise CoolbotError("Unloaded before connecting")
        session = async_get_clientsession(self.hass)
        client = CoolbotClient(
            self.config_entry.data[CONF_EMAIL],
            self.config_entry.data[CONF_PASSWORD],
            session=session,
        )
        handed_over = False
        try:
            await client.async_connect()
            handed_over = not self._closed
        finally:
            if not handed_over:
                # Nothing else holds this client yet, and its socket is already
                # open, so every way of leaving without it has to close it here,
                # cancellation and a teardown that ran meanwhile included.
                await client.async_close()
        if not handed_over:
            raise CoolbotError("Unloaded while connecting")

        # Connecting reads the profile, so the clock starts here.
        self._profile_read_at = dt_util.utcnow()
        self._client = client
        self._remove_listener = client.add_listener(self._handle_push)

    @callback
    def _handle_push(self) -> None:
        """Publish the moment a cooler reports.

        This is the whole point of the integration being push: nothing here
        waits for a timer, so a reading reaches entities as it lands.
        """
        if self._client is None:
            return
        self.async_set_updated_data(self._build(self._client.get_devices()))

    @override
    @callback
    def async_set_updated_data(self, data: dict[str, CoolbotDevice]) -> None:
        """Publish data, logging a recovery the way a refresh does.

        Maintenance and pushes publish here rather than through a refresh,
        so without this a failure would be logged but its end would not.
        """
        if not self.last_update_success:
            self.logger.info("Fetching %s data recovered", self.name)
        super().async_set_updated_data(data)

    @override
    async def _async_update_data(self) -> dict[str, CoolbotDevice]:
        """Build the current state.

        Pushes publish directly, so this runs for the first refresh and for
        anything that asks for one explicitly, not on a schedule.
        """
        try:
            await self._async_ensure_connected()
        except CoolbotAuthError as err:
            raise self._auth_error(err) from err
        except CoolbotError as err:
            raise self._connection_error(err) from err

        assert self._client is not None
        return self._build(self._client.get_devices())

    async def _async_ensure_connected(self) -> None:
        """Reconnect if the socket has gone."""
        async with self._connect_lock:
            if self._client is not None and self._client.connected:
                return
            _LOGGER.debug("Socket is down, reconnecting")
            await self._async_shutdown_client()
            # Nothing is published while this runs, so an unbounded stall
            # would leave the last readings showing; failing in time lets the
            # error mark them unavailable instead. Cancellation closes the
            # half-open client in _async_connect.
            try:
                async with asyncio.timeout(CONNECT_TIMEOUT_SECONDS):
                    await self._async_connect()
            except TimeoutError as err:
                raise CoolbotError("Timed out reconnecting") from err

    @callback
    def _schedule_maintenance(self, _now: datetime) -> None:
        """Start a maintenance pass, unless the last one is still running."""
        if self._maintenance_task is not None and not self._maintenance_task.done():
            # Staleness is a function of time, not of the network: a pass held
            # up by a reconnect or a ping must not keep a cooler that stopped
            # reporting showing its last reading for as long as it takes.
            if self.data:
                self.async_update_listeners()
            return
        self._maintenance_task = self.config_entry.async_create_task(
            self.hass, self._async_maintain(), "coolbot maintenance"
        )

    async def _async_maintain(self) -> None:
        """Hold the connection open and re-examine what has gone quiet.

        No readings are fetched here. They arrive by push; this keeps the socket
        usable and republishes so that a cooler which has stopped reporting is
        noticed, since silence produces no callback to notice it by.
        """
        client: CoolbotClient | None = None
        try:
            await self._async_ensure_connected()
            client = self._client
            assert client is not None
            await client.async_ping()
            await self._async_reread_profile_if_due(client)
            devices = client.get_devices()
        except CoolbotAuthError as err:
            if self._superseded(client):
                return
            # Published before the close is awaited, in both handlers: a
            # refresh can reconnect while the old socket closes, and its
            # healthy data must land after this error, not be overwritten by it.
            self.async_set_update_error(self._auth_error(err))
            # The socket must not be left open while the credentials are wrong.
            await self._async_shutdown_client()
            return
        except CoolbotError as err:
            if self._superseded(client):
                return
            self.async_set_update_error(self._connection_error(err))
            # Dropped so the next pass reconnects from scratch.
            await self._async_shutdown_client()
            return

        if self._superseded(client):
            return
        self.async_set_updated_data(self._build(devices))

    def _superseded(self, client: CoolbotClient | None) -> bool:
        """Whether a refresh replaced this pass's client while it waited on it.

        The outcome then belongs to a socket already closed, and acting on it
        would close the healthy replacement or publish what it has outdated.
        """
        return client is not None and client is not self._client

    def _auth_error(self, err: CoolbotError) -> ConfigEntryError:
        """Wrap a rejected login.

        Not ConfigEntryAuthFailed: that asks Home Assistant to start a reauth
        flow, and this integration has none yet. Raising it would offer the user
        a repair that cannot open. Swap it back when reauth lands.
        """
        return ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
            translation_placeholders={"error": str(err)},
        )

    def _connection_error(self, err: CoolbotError) -> UpdateFailed:
        """Wrap a failure to reach the service."""
        return UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"error": str(err)},
        )

    def _build(self, devices: list[CoolbotDevice]) -> dict[str, CoolbotDevice]:
        """Turn the client's device list into what entities read.

        An empty list is a valid answer, not a failure: the profile is
        authoritative, and treating it as an error would retain the previous
        devices forever, leaving the last removed cooler undeletable and a
        reload stuck retrying.
        """
        data: dict[str, CoolbotDevice] = {}
        for device in devices:
            if device.is_provisioned and not device.mac_address:
                # The MAC is the stable identity behind unique_id; publishing
                # under the dash/slot fallback would duplicate the device once
                # it arrives, and the client left it unset precisely because
                # the slot cannot be vouched for yet.
                _LOGGER.debug(
                    "Holding back %s until its MAC address arrives", device.name
                )
                continue
            data[device.unique_id] = device

        self._apply_late_device_details(data)
        return data

    async def _async_reread_profile_if_due(self, client: CoolbotClient) -> None:
        """Re-read the account profile from time to time.

        The client reads it while connecting and then serves the device list
        from it, so without this a cooler added to or removed from the account
        would go unnoticed until the socket happened to reconnect.
        """
        now = dt_util.utcnow()
        if (
            self._profile_read_at is not None
            and now - self._profile_read_at < PROFILE_REFRESH_INTERVAL
        ):
            return
        await client.async_refresh_profile()
        self._profile_read_at = now

    def _apply_late_device_details(self, data: dict[str, CoolbotDevice]) -> None:
        """Record device details that change after a cooler is created.

        Connecting waits for the pins that identify a cooler, not for all of
        them, so it can be registered before its model and firmware arrive.
        Device info is only read when an entity is added, so without this those
        details would stay missing until the entry is reloaded. The name rides
        along so a cooler renamed in the account is renamed here too; a name
        the user chose in Home Assistant still wins over it.
        """
        registry = dr.async_get(self.hass)
        for unique_id, device in data.items():
            details = (
                device.name,
                device_model(device),
                device.jumper_firmware,
                device.jumper_hardware,
            )
            if self._device_details.get(unique_id) == details:
                continue
            entry = registry.async_get_device_by_identifier(
                (DOMAIN, unique_id), self.config_entry.entry_id
            )
            if entry is None:
                # Its entities have not been created yet, so it will be
                # registered with whatever has replayed by then.
                continue
            self._device_details[unique_id] = details
            current = (entry.name, entry.model, entry.sw_version, entry.hw_version)
            if current == details:
                continue
            registry.async_update_device(
                entry.id,
                name=details[0],
                model=details[1],
                sw_version=details[2],
                hw_version=details[3],
            )

    @override
    async def async_shutdown(self) -> None:
        """Stop the timer and close the socket."""
        await super().async_shutdown()
        await self._async_teardown()

    async def _async_teardown(self) -> None:
        """Release everything setup acquired. Safe to call more than once."""
        self._closed = True
        if self._unsub_stop is not None:
            self._unsub_stop()
            self._unsub_stop = None
        if self._cancel_maintenance is not None:
            self._cancel_maintenance()
            self._cancel_maintenance = None
        if self._maintenance_task is not None:
            # Stopped and awaited before the client is closed, so a pass
            # cannot reconnect behind the close. Cancelling one mid-connect is
            # safe: _async_connect closes a client it has not handed over.
            task, self._maintenance_task = self._maintenance_task, None
            task.cancel()
            await asyncio.wait((task,))
        await self._async_shutdown_client()

    async def _async_shutdown_client(self) -> None:
        if self._remove_listener is not None:
            # Before the client goes: a listener left on a discarded client
            # would publish readings from a socket nothing is maintaining.
            self._remove_listener()
            self._remove_listener = None
        if self._client is not None:
            client, self._client = self._client, None
            # async_close is guaranteed by the library not to raise, so a
            # failed close cannot mask whatever prompted the shutdown.
            await client.async_close()


def device_model(device: CoolbotDevice) -> str:
    """Return the model name, including the hardware revision once known."""
    if device.coolbot_hardware:
        return f"CoolBot Pro {device.coolbot_hardware}"
    return "CoolBot Pro"


def device_is_fresh(device: CoolbotDevice) -> bool:
    """Whether a device's readings should be trusted right now.

    A CoolBot that loses WiFi leaves the cloud serving its last known values, so
    a stale reading looks current. Entities go unavailable rather than reporting
    a temperature that has stopped moving.
    """
    if not device.is_provisioned:
        return False
    age = device.data_age_seconds
    if age is None:
        # The server replays a cached snapshot on connect that can be minutes
        # old, so nothing is trustworthy until a live push arrives this session.
        return False
    return age <= STALE_AFTER_SECONDS
