"""The Hikvision integration."""

import asyncio
from collections.abc import Awaitable, Callable
import contextlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import Any
import uuid
from xml.etree.ElementTree import ParseError

from pyhik.constants import NVR_DEVICE, SENSOR_MAP
from pyhik.hikvision import HikCamera, VideoChannel, get_video_channels
from pyhik.image import ImageChannelInfo
from pyhik.isapi import (
    ISAPIAuthError,
    ISAPIClient,
    ISAPIConnectionError,
    ISAPIError,
    ISAPINotSupportedError,
)
import requests

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_RANDOM_ID, CONF_RECORDER, DOMAIN
from .coordinator import (
    HikvisionImageClient,
    HikvisionImageCoordinator,
    async_complete,
    async_run_to_end,
    async_start_reauth,
    async_stop_stream,
    log_credentials_rejected,
)
from .identity import (
    ambiguous_identities_issue_id,
    async_earlier_devices,
    async_earlier_entities,
    async_link_to_kept_devices,
    async_move_device,
    decode_ambiguous_identities,
    encode_ambiguous_identities,
    is_made_up_id,
    is_random_id_made_up,
    looks_made_up,
    oldest,
)

_LOGGER = logging.getLogger(__name__)

# How long to wait before trying the image settings again after a failed read
IMAGE_SETTINGS_RETRY_INTERVAL = timedelta(minutes=5)

# What the event stream feeds. These are set up before the image settings are
# read: a camera that is slow to answer must not hold back the events of its stream.
EVENT_PLATFORMS = [Platform.BINARY_SENSOR, Platform.CAMERA, Platform.EVENT]
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.EVENT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class HikvisionData:
    """Data class for Hikvision runtime data."""

    camera: HikCamera
    # What the entities and the device are registered under: stable, unlike the ID
    # pyHik makes up for a device whose own ID is too short.
    device_id: str
    # What pyHik puts in front of the events of the stream: the ID it gives now.
    stream_id: str
    device_name: str
    device_type: str
    # An NVR, or a recorder that reports the type of a camera: its attached
    # cameras are read through it, each on a device of its own.
    is_nvr: bool
    host: str
    username: str
    password: str
    channels: dict[int, VideoChannel] = field(default_factory=dict)
    # A standalone camera has one, an NVR one per attached camera: they share the
    # client and the login.
    image_coordinators: list[HikvisionImageCoordinator] = field(default_factory=list)
    # The stop of the event stream, shared by everything that stops it
    stream_stop: asyncio.Task[None] | None = None
    # Set once the device refused the password of the event stream, or of a retry
    # of the image settings: nothing sends it again, until new credentials reload
    # the entry.
    login_rejected: bool = False
    # The settings of the entry this setup connected with
    connection: dict[str, object] = field(default_factory=dict)


type HikvisionConfigEntry = ConfigEntry[HikvisionData]


@callback
def _async_record_random_id(
    hass: HomeAssistant, entry: HikvisionConfigEntry, camera_id: object
) -> None:
    """Record where an older entry's ID came from, once the device settles it.

    The device answering with the entry's ID as its own shows it is its own; it
    answering with a random made-up one, for an entry whose ID has that form, shows
    pyHik made that one up too. Anything else settles nothing, and the form of the
    ID stays the guess.
    """
    if CONF_RANDOM_ID in entry.data:
        return
    if not isinstance(camera_id, uuid.UUID) and str(camera_id) == str(entry.unique_id):
        random_id = False
    elif is_random_id_made_up(camera_id) and looks_made_up(entry.unique_id):
        random_id = True
    else:
        return
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_RANDOM_ID: random_id}
    )


@callback
def _async_adopt_made_up_identities(
    hass: HomeAssistant, entry: HikvisionConfigEntry, device_id: str
) -> None:
    """Move the devices and entities of earlier made-up IDs to the entry's own ID.

    Before the entry kept its ID, each setup registered them under the random ID
    pyHik made up on that connection, which differs from the one the entry was
    created with. Of the ones each stands for, the first registered is kept: it
    has the entity ID automations use, and the device the user set up. One the
    entry's ID already has is left as it is.

    When the first cannot be told, because the registry gave them all the same
    date of creation, none is moved: a repair issue asks the user which to keep.
    """
    dev_reg = dr.async_get(hass)
    # The identifiers of the entry's devices, channel devices included.
    taken = {
        identifier
        for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
        for identifier in device.identifiers
    }
    ambiguous_devices: list[str] = []
    for rest, devices in async_earlier_devices(hass, entry, device_id).items():
        new_identifier = (DOMAIN, device_id + rest)
        if new_identifier in taken:
            continue
        if (first_device := oldest(devices, lambda item: item[0].created_at)) is None:
            ambiguous_devices.append(rest)
            continue
        async_move_device(hass, *first_device, new_identifier)

    ent_reg = er.async_get(hass)
    ambiguous_entities: list[list[str]] = []
    for (domain, rest), entities in async_earlier_entities(
        hass, entry, device_id
    ).items():
        new_unique_id = device_id + rest
        if ent_reg.async_get_entity_id(domain, DOMAIN, new_unique_id) is not None:
            continue
        if (first_entity := oldest(entities, lambda entity: entity.created_at)) is None:
            ambiguous_entities.append([domain, rest])
            continue
        ent_reg.async_update_entity(first_entity.entity_id, new_unique_id=new_unique_id)

    if ambiguous_devices or ambiguous_entities:
        _async_ask_which_identities_to_keep(
            hass, entry, ambiguous_devices, ambiguous_entities
        )


@callback
def _async_ask_which_identities_to_keep(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    devices: list[str],
    entities: list[list[str]],
) -> None:
    """Create the repair issue that asks which earlier devices and entities to keep.

    The setup goes on meanwhile, with new ones under the entry's ID; the repair
    can then put a chosen earlier one in place of each. Kept with what an issue
    created by an earlier setup asks, which that setup's new ones now hide.
    """
    issue_id = ambiguous_identities_issue_id(entry.entry_id)
    if (
        issue := ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    ) is not None and issue.data:
        earlier_devices, earlier_entities = decode_ambiguous_identities(issue.data)
        # One question each: one the camera no longer has is found again by each
        # setup, as nothing takes its place.
        devices = list(dict.fromkeys([*earlier_devices, *devices]))
        entities = [
            list(entity)
            for entity in dict.fromkeys(map(tuple, [*earlier_entities, *entities]))
        ]
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        config_entry_id=entry.entry_id,
        data=encode_ambiguous_identities(entry.entry_id, devices, entities),
        is_fixable=True,
        # Not raised again by the next setup: its new ones hold the entry's ID.
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="ambiguous_identities",
        translation_placeholders={"name": entry.title},
    )


async def async_setup_entry(hass: HomeAssistant, entry: HikvisionConfigEntry) -> None:
    """Set up Hikvision from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    ssl = entry.data[CONF_SSL]
    # Entries created before the option existed always verified the certificate
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)

    protocol = "https" if ssl else "http"
    url = f"{protocol}://{host}"

    try:
        camera = await hass.async_add_executor_job(
            HikCamera, url, port, username, password, verify_ssl
        )
    except requests.exceptions.RequestException as err:
        raise ConfigEntryNotReady(f"Unable to connect to {host}") from err

    if (camera_id := camera.get_id) is None:
        if camera.auth_failed:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            )
        raise ConfigEntryNotReady(f"Unable to get device ID from {host}")
    stream_id = str(camera_id)
    device_id = stream_id
    _async_record_random_id(hass, entry, camera_id)
    made_up = isinstance(camera_id, uuid.UUID) and is_made_up_id(entry)
    if made_up:
        # pyHik before 0.5.1 makes up a random ID for a device whose own ID is too
        # short, a new one at every connection. An entry created with such an ID
        # keeps it, so its device and entities stay the same. An entry with a real
        # or derived ID does not lend it: a camera that answers with a made-up ID
        # is not known to be the one it was created for.
        device_id = str(entry.unique_id)
        _async_adopt_made_up_identities(hass, entry, device_id)

    device_name = camera.get_name or host
    device_type = camera.get_type or "Camera"
    is_nvr = device_type == "NVR" or entry.data.get(CONF_RECORDER, False)
    if is_nvr:
        # Also a recorder that reports a camera type: pyHik only asks for the video
        # of each of its cameras by channel once it knows the device is a recorder.
        camera.device_type = NVR_DEVICE

    # For NVRs, fetch video channel information
    channels: dict[int, VideoChannel] = {}
    if is_nvr:
        channel_list = await hass.async_add_executor_job(
            get_video_channels, host, port, username, password, ssl, verify_ssl
        )
        channels = {ch.id: ch for ch in channel_list}
        _LOGGER.debug("Found %d video channels", len(channels))

    entry.runtime_data = HikvisionData(
        camera=camera,
        device_id=device_id,
        stream_id=stream_id,
        device_name=device_name,
        device_type=device_type,
        is_nvr=is_nvr,
        host=host,
        username=username,
        password=password,
        channels=channels,
        connection=_connection_settings(entry),
    )

    _LOGGER.debug(
        "Device %s (type=%s) initial event_states: %s",
        device_name,
        device_type,
        camera.current_event_states,
    )

    # For NVRs or devices with no detected events, try to fetch events from ISAPI
    # Use broader notification methods for NVRs since they often use 'record' etc.
    if is_nvr or not camera.current_event_states:
        nvr_notification_methods = {"center", "HTTP", "record", "email", "beep"}

        def fetch_and_inject_nvr_events() -> None:
            """Fetch and inject NVR events in a single executor job."""
            try:
                nvr_events = camera.get_event_triggers(nvr_notification_methods)
            except (requests.exceptions.RequestException, ParseError) as err:
                _LOGGER.warning("Unable to fetch event triggers from %s: %s", host, err)
                return

            _LOGGER.debug("NVR events fetched with extended methods: %s", nvr_events)
            if nvr_events:
                # Map raw event type names to friendly names using SENSOR_MAP
                mapped_events: dict[str, list[int]] = {}
                for event_type, channels in nvr_events.items():
                    event_key = event_type.lower()
                    # Skip videoloss - used as watchdog by pyhik, not a real sensor
                    if event_key == "videoloss":
                        continue
                    friendly_name = SENSOR_MAP.get(event_key)
                    if friendly_name is None:
                        _LOGGER.debug("Skipping unmapped event type: %s", event_type)
                        continue
                    if friendly_name in mapped_events:
                        mapped_events[friendly_name].extend(channels)
                    else:
                        mapped_events[friendly_name] = list(channels)
                _LOGGER.debug("Mapped NVR events: %s", mapped_events)
                if mapped_events:
                    camera.inject_events(mapped_events)
            else:
                _LOGGER.debug(
                    "No event triggers returned from %s. "
                    "Ensure events are configured on the device",
                    host,
                )

        await hass.async_add_executor_job(fetch_and_inject_nvr_events)

    # Start the event stream
    await hass.async_add_executor_job(camera.start_stream)

    async def _async_stop_stream(event: Event) -> None:
        # Home Assistant does not unload the entry when it stops: the image settings
        # client is closed here too.
        try:
            await async_stop_stream(hass, entry.runtime_data)
        finally:
            await _async_close_image_settings(entry.runtime_data)

    # pyHik's stream thread is non-daemonic and publishes straight into hass, so
    # it has to be joined before the event loop closes. Starting it yields, so
    # the stop event may already have been fired by the time we get here, and
    # listening for it now would never hear it.
    if hass.is_stopping:
        await async_stop_stream(hass, entry.runtime_data)
        raise ConfigEntryNotReady("Home Assistant is stopping")

    # The entry can be unloaded after the stop, when a one-time listener is gone.
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _async_stop_stream)
    )

    # Register the main device before platforms that use via_device
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_id)},
        name=device_name,
        manufacturer="Hikvision",
        model=device_type,
    )
    if made_up:
        async_link_to_kept_devices(hass, entry, device_id)

    # Without waiting for the image settings: the stream is already running, and
    # an event that arrives before its entities exist would be lost.
    event_platforms = [p for p in PLATFORMS if p in EVENT_PLATFORMS]
    image_platforms = [p for p in PLATFORMS if p not in EVENT_PLATFORMS]
    # Every platform whose setup was started: a setup that is cancelled, or fails,
    # halfway through forwarding can leave some of them set up.
    forwarded = list(event_platforms)

    try:
        await hass.config_entries.async_forward_entry_setups(entry, event_platforms)

        entry.runtime_data.image_coordinators = await _async_setup_image_settings(
            hass,
            entry,
            host,
            port,
            username,
            password,
            ssl,
            verify_ssl,
            is_nvr,
        )
        if hass.is_stopping:
            # The stop closed what it found before the discovery ended: the client
            # is closed here instead, and has no entities.
            await _async_close_image_settings(entry.runtime_data)
            entry.runtime_data.image_coordinators = []

        if image_platforms:
            forwarded.extend(image_platforms)
            await hass.config_entries.async_forward_entry_setups(entry, image_platforms)

        entry.async_on_unload(_async_watch_stream_credentials(hass, entry))
    except BaseException:

        async def _async_clean_up() -> None:
            # A setup that fails, or is cancelled, does not call async_unload_entry,
            # so what it started is stopped here, each step even if one before it
            # failed: the platforms it forwarded, or else the next setup would find
            # them already set up...
            try:
                await hass.config_entries.async_unload_platforms(entry, forwarded)
            finally:
                try:
                    # ...the image settings client, if the image platforms failed
                    # after it...
                    await _async_close_image_settings(entry.runtime_data)
                finally:
                    # ...and the thread of the stream, which would keep the process
                    # from ending, unless a rejected password stopped it already.
                    await async_stop_stream(hass, entry.runtime_data)

        try:
            # To its end, even if the setup is cancelled again meanwhile.
            await async_complete(_async_clean_up())
        except Exception:
            # Why the setup failed is what matters (a retry, or reauth): an error
            # while cleaning up does not replace it.
            _LOGGER.exception("Error while cleaning up after a failed setup")
        raise


async def _async_login_rejected(
    hass: HomeAssistant, entry: HikvisionConfigEntry
) -> None:
    """Stop everything that would send a password the device refuses, and ask again.

    The stream and the image settings use the same login.
    """
    data = entry.runtime_data
    data.login_rejected = True
    if coordinators := data.image_coordinators:
        # Stops the stream too, and asks for new credentials.
        await coordinators[0].async_stream_rejected()
        return
    try:
        await async_stop_stream(hass, data)
    except Exception:
        # New credentials are asked for all the same: nothing else would.
        _LOGGER.exception(
            "Error while stopping the event stream of %s", data.device_name
        )
    # Not once the entry is going away, or set up again with a stream of its own.
    if (
        hass.is_stopping
        or entry.state is not ConfigEntryState.LOADED
        or getattr(entry, "runtime_data", None) is not data
    ):
        return
    log_credentials_rejected(entry)
    async_start_reauth(hass, entry)


# What the watch of the credentials is registered for, after the ID of the stream:
# no event has this name. pyHik calls every callback when its stream changes state.
STREAM_CREDENTIALS = "stream_credentials"


@callback
def _async_watch_stream_credentials(
    hass: HomeAssistant, entry: HikvisionConfigEntry
) -> Callable[[], None]:
    """Ask for new credentials when the event stream is refused them.

    The stream is the only thing that talks to every device all the time, so it is
    the first to notice a changed password, also on a device with no image
    settings, or with all of them disabled. pyHik slows the stream down when it
    happens, so that the account is not locked by retries, but does not give up: the
    stream is stopped here, and so are the image settings, which use the same login.
    Reauthentication reloads the entry, with a new stream. Returns what stops the
    watch.
    """
    data = entry.runtime_data
    camera = data.camera
    handled = False

    @callback
    def _async_check() -> None:
        nonlocal handled
        # Not once the stream is being stopped: on purpose, or by a request that
        # found the password rejected, which deals with it.
        if (
            handled
            or data.login_rejected
            or not camera.stream_auth_failed
            or data.stream_stop is not None
        ):
            return
        handled = True
        entry.async_create_background_task(
            hass,
            async_complete(_async_login_rejected(hass, entry)),
            f"{DOMAIN} stream credentials",
        )

    def _changed(_sensor: str) -> None:
        # From the thread of the stream.
        with contextlib.suppress(RuntimeError):
            hass.loop.call_soon_threadsafe(_async_check)

    watch = f"{data.stream_id}.{STREAM_CREDENTIALS}"
    camera.add_update_callback(_changed, watch)
    # It may have been refused before this was registered.
    _async_check()
    return lambda: camera.remove_update_callback(_changed, watch)


async def _async_setup_image_settings(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    host: str,
    port: int,
    username: str,
    password: str,
    ssl: bool,
    verify_ssl: bool,
    is_nvr: bool,
) -> list[HikvisionImageCoordinator]:
    """Discover the image settings of a camera, or of the cameras of an NVR.

    Image settings are an optional extra: a device that does not offer them, or
    does not allow reading them, simply gets no image entities.
    """

    async def _async_close_unused(unused: ISAPIClient) -> None:
        """Close a client made for a setup that was cancelled meanwhile."""
        await async_run_to_end(hass, unused.close)

    client = await async_run_to_end(
        hass,
        ISAPIClient,
        host,
        port,
        username,
        password,
        ssl,
        verify_ssl,
        on_result=_async_close_unused,
    )
    # Shared with the coordinators: the client is closed once, whichever closes it.
    shared = HikvisionImageClient(client)

    async def _async_close() -> None:
        """Close the client, once and to its end, whatever path asks first.

        Under the lock: the cameras of an NVR found so far can be reached meanwhile,
        by the diagnostics for one, and the client is not closed under a request
        that is still running.
        """
        if shared.closed:
            return

        async def _async_close_now() -> None:
            async with shared.lock:
                if shared.closed:
                    return
                await async_run_to_end(hass, client.close)
                shared.closed = True

        try:
            await async_complete(_async_close_now())
        except Exception:
            # Why the client is closed (no image settings, a rejected password, a
            # failed setup) matters more than the close: it is not replaced. Not
            # marked closed, so a later path can try again.
            _LOGGER.exception("Error closing the image settings client of %s", host)

    discovery = _ImageDiscovery(hass, entry, host, shared, _async_close)
    try:
        if is_nvr:
            coordinators = await discovery.async_nvr_cameras()
        else:
            coordinators = await discovery.async_camera()
    except BaseException:
        # Anything unexpected, or a cancelled setup, must not leave it open. Not
        # closed twice: a path that already closed it is not repeated.
        await _async_close()
        raise
    if discovery.retries:
        _async_retry_image_settings_later(
            hass,
            entry,
            discovery.retries,
            (host, port, username, password, ssl, verify_ssl),
        )
    if not coordinators:
        await _async_close()
    return coordinators


class _ImageDiscovery:
    """Read the image settings of a device with a new client.

    The cameras of an NVR are read through its proxy endpoints, with the channel
    IDs it lists, and share the client.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HikvisionConfigEntry,
        host: str,
        shared: HikvisionImageClient,
        close: Callable[[], Awaitable[None]],
    ) -> None:
        """Initialize the discovery."""
        self._hass = hass
        self._entry = entry
        self._host = host
        self._shared = shared
        self._close = close
        # What failed and may work later, to read again.
        self.retries: list[_Probe] = []
        # Found to be a recorder: set up again as one, nothing more is read.
        self._recorder = False

    def _retry(self, probe: _Probe) -> None:
        """Read this again later."""
        if probe not in self.retries:
            self.retries.append(probe)

    async def _async_send[_T](self, job: Callable[[], _T]) -> _T:
        """Send a discovery request, one at a time on the client.

        The cameras of an NVR found so far can be reached meanwhile, by the
        diagnostics for one, while the next ones are read. So a request waits for
        theirs, to its end even if the setup is cancelled (the client is closed
        after it), and is not sent once one of them, or the event stream, got the
        credentials rejected, or the client was closed, as it is when Home
        Assistant stops.
        """
        shared = self._shared
        camera = self._entry.runtime_data.camera

        def _send() -> _T:
            # A busy executor can start the job late: the stream may have had the
            # password rejected meanwhile. Not sent then.
            if camera.stream_auth_failed:
                raise ISAPIAuthError("The device rejected the credentials", 401)
            return job()

        async with shared.lock:
            # The stream runs before the discovery, and may have been refused the
            # password already: its watch only starts once the setup ends.
            if shared.credentials_rejected or camera.stream_auth_failed:
                # Sending them again could lock the account.
                raise ISAPIAuthError("The device rejected the credentials", 401)
            if shared.closed:
                raise ConfigEntryNotReady("The image settings client is closed")
            try:
                return await async_run_to_end(self._hass, _send)
            except ISAPIAuthError as err:
                if err.status_code == 401:
                    shared.credentials_rejected = True
                raise

    async def _async_rejected(self) -> ConfigEntryAuthFailed:
        """Stop what uses the rejected password, and return the error to raise.

        The device rejects the credentials, not just this request. The event stream
        would keep using them, so it is stopped before new ones are asked for.
        """
        await self._close()
        try:
            await async_stop_stream(self._hass, self._entry.runtime_data)
        except Exception:
            # Still ask for new credentials: the clean-up of the failed setup
            # tries to stop the stream again.
            _LOGGER.exception("Error stopping the event stream of %s", self._host)
        return ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        )

    async def _async_first_refresh(
        self, coordinator: HikvisionImageCoordinator, what: str, probe: _Probe
    ) -> bool:
        """Read the first values; return whether they could be read."""
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady as err:
            # The events work without the image settings, so do not hold them back.
            _LOGGER.warning("Unable to read the image values of %s: %s", what, err)
            if _may_work_later(err):
                self._retry(probe)
            return False
        return True

    async def _async_detections_only(
        self,
        found: list[HikvisionImageCoordinator],
        channel: int | None,
        what: str,
    ) -> HikvisionImageCoordinator | None:
        """Find the detections of a camera whose image settings were not found.

        Its detections can still be turned on and off. None if it has none.
        """
        coordinator = HikvisionImageCoordinator(
            self._hass, self._entry, self._shared, [], channel
        )
        data = self._entry.runtime_data
        # During its first refresh: a 401 there stops the others too.
        data.image_coordinators = [*found, coordinator]
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady as err:
            _LOGGER.debug("Unable to read the detections of %s: %s", what, err)
            return None
        finally:
            data.image_coordinators = found
        return coordinator if coordinator.detections else None

    async def async_camera(self) -> list[HikvisionImageCoordinator]:
        """Discover the image settings and detections of a standalone camera."""
        coordinators = await self._async_camera_image_settings()
        if coordinators or self._recorder:
            return coordinators
        if (
            coordinator := await self._async_detections_only([], None, self._host)
        ) is None:
            return []
        return [coordinator]

    async def _async_camera_image_settings(self) -> list[HikvisionImageCoordinator]:
        """Discover the image settings of a standalone camera."""
        host = self._host
        try:
            # To its end even if the setup is cancelled: the client is closed after
            # it.
            settings = await self._async_send(self._shared.client.get_image_settings)
        except ISAPIAuthError as err:
            if err.status_code == 401:
                raise await self._async_rejected() from err
            _LOGGER.warning(
                "Not allowed to read the image settings of %s: %s", host, err
            )
            return []
        except ISAPIConnectionError as err:
            _LOGGER.warning("Unable to read the image settings of %s: %s", host, err)
            self._retry(READ_CAMERA)
            return []
        except ISAPIError as err:
            # Some recorders report the type of a camera, so the device type cannot
            # tell them apart. They answer the camera's endpoints with an error, but
            # list the cameras attached to them on the NVR's.
            if await self._async_list_image_channels(quiet=True):
                self._async_set_up_as_a_recorder()
                self._recorder = True
                return []
            if isinstance(err, ISAPINotSupportedError):
                _LOGGER.debug("%s does not support image settings", host)
            else:
                _LOGGER.warning(
                    "Unable to read the image settings of %s: %s", host, err
                )
                if _may_work_later(err):
                    self._retry(READ_CAMERA)
            return []
        coordinator = HikvisionImageCoordinator(
            self._hass, self._entry, self._shared, settings
        )
        if not await self._async_first_refresh(coordinator, host, READ_CAMERA):
            return []
        return [coordinator]

    @callback
    def _async_set_up_as_a_recorder(self) -> None:
        """Record that the device is a recorder, and set it up again as one.

        Everything else was set up as for a camera: its events and its video on
        the device of the recorder. Set up as an NVR, each attached camera gets a
        device of its own, with its events, its video and its image settings.
        """
        _async_record_recorder(self._hass, self._entry)
        # Once this setup ends: a reload waits for it.
        self._hass.config_entries.async_schedule_reload(self._entry.entry_id)

    async def _async_list_image_channels(
        self, *, quiet: bool
    ) -> list[ImageChannelInfo]:
        """Return the enabled cameras an NVR lists, or none if it cannot list them.

        With ``quiet`` a failure to list them is only logged for debugging, as the
        device may simply not be an NVR.
        """
        host = self._host
        try:
            image_channels = await self._async_send(
                partial(self._shared.client.get_image_channels, proxy=True)
            )
        except ISAPIError as err:
            if isinstance(err, ISAPIAuthError) and err.status_code == 401:
                raise await self._async_rejected() from err
            if _may_work_later(err):
                # Whether it is logged or not: the device may only have been busy.
                self._retry(LIST_CHANNELS)
            if quiet or isinstance(err, ISAPINotSupportedError):
                _LOGGER.debug("%s does not list image channels: %s", host, err)
            elif isinstance(err, ISAPIAuthError):
                _LOGGER.warning(
                    "Not allowed to read the image settings of %s: %s", host, err
                )
            else:
                _LOGGER.warning(
                    "Unable to read the image settings of %s: %s", host, err
                )
            return []
        return [
            image_channel
            for image_channel in image_channels
            if image_channel.enabled is not False
        ]

    async def async_nvr_cameras(self) -> list[HikvisionImageCoordinator]:
        """Discover the image settings of the cameras attached to an NVR.

        And the detections of each, also of a camera whose image settings were not
        found.
        """
        host = self._host
        coordinators: list[HikvisionImageCoordinator] = []
        listed = [
            image_channel.id
            for image_channel in await self._async_list_image_channels(quiet=False)
        ]
        # Without a list of its cameras, the video channels of the NVR: their
        # detections can still be turned on and off.
        for channel in listed or sorted(self._entry.runtime_data.channels):
            what = f"channel {channel} of {host}"
            coordinator = None
            if channel in listed:
                coordinator = await self._async_channel_image_settings(
                    coordinators, channel, what
                )
            if coordinator is None:
                coordinator = await self._async_detections_only(
                    coordinators, channel, what
                )
            if coordinator is not None:
                coordinators.append(coordinator)
        self._entry.runtime_data.image_coordinators = coordinators
        return coordinators

    async def _async_channel_image_settings(
        self, found: list[HikvisionImageCoordinator], channel: int, what: str
    ) -> HikvisionImageCoordinator | None:
        """Discover the image settings of a camera attached to an NVR."""
        client = self._shared.client
        try:
            settings = await self._async_send(
                partial(client.get_image_settings, channel, proxy=True)
            )
        except ISAPINotSupportedError:
            # The NVR may list a camera that it cannot proxy.
            _LOGGER.debug("%s has no image settings", what)
            return None
        except ISAPIError as err:
            if isinstance(err, ISAPIAuthError) and err.status_code == 401:
                raise await self._async_rejected() from err
            _LOGGER.warning("Unable to read the image settings of %s: %s", what, err)
            if _may_work_later(err):
                self._retry(read_channel(channel))
            return None
        coordinator = HikvisionImageCoordinator(
            self._hass, self._entry, self._shared, settings, channel
        )
        # Before its first refresh: a 401 there stops the others too.
        self._entry.runtime_data.image_coordinators = [*found, coordinator]
        if await self._async_first_refresh(coordinator, what, read_channel(channel)):
            return coordinator
        self._entry.runtime_data.image_coordinators = found
        return None


async def _async_close_image_settings(data: HikvisionData) -> None:
    """Stop the polling of every camera, then close the client they share.

    The client is closed once no request is using it.
    """
    coordinators = data.image_coordinators
    for coordinator in coordinators[1:]:
        await coordinator.async_shutdown()
    if coordinators:
        await coordinators[0].async_close()


def _may_work_later(err: BaseException) -> bool:
    """Return whether a failed read may work if it is tried again later.

    Only a camera that could not be reached, or answered that it cannot serve the
    request now (an HTTP 5xx is how a busy camera answers), may answer later. One
    that does not allow the read, or does not have it, will not change its mind,
    and neither will an answer that could not be read: trying again would only
    reload the entry, and restart its event stream, every few minutes.

    The first refresh wraps the error of the camera, so the causes are followed.
    """
    cause: BaseException | None = err
    while cause is not None:
        if isinstance(cause, ISAPIConnectionError):
            return True
        if isinstance(cause, ISAPIError):
            return (
                not isinstance(cause, (ISAPIAuthError, ISAPINotSupportedError))
                and cause.status_code is not None
                and cause.status_code >= 500
            )
        cause = cause.__cause__
    return False


# Reads again a part of the image settings that could not be read: the requests to
# make one after the other, each with the client given to it. They are separate, so
# that nothing more is sent once the password is known to be refused.
type _Step = Callable[[ISAPIClient], object]
type _Probe = tuple[_Step, ...]


class _RetryRejected(Exception):
    """The password was rejected while a step of the retry waited to run."""


def _get_settings(client: ISAPIClient) -> None:
    """Read the image settings of a standalone camera."""
    client.get_image_settings()


def _get_values(client: ISAPIClient) -> None:
    """Read the image values of a standalone camera."""
    client.get_image_values()


def _get_channels(client: ISAPIClient) -> bool:
    """List the image channels of an NVR; return whether it lists a camera."""
    return any(
        channel.enabled is not False
        for channel in client.get_image_channels(proxy=True)
    )


def _get_channel_settings(client: ISAPIClient, channel: int) -> None:
    """Read the image settings of a camera attached to an NVR."""
    client.get_image_settings(channel, proxy=True)


def _get_channel_values(client: ISAPIClient, channel: int) -> None:
    """Read the image values of a camera attached to an NVR."""
    client.get_image_values(channel, proxy=True)


@callback
def _async_record_recorder(hass: HomeAssistant, entry: HikvisionConfigEntry) -> None:
    """Record that a device that reports the type of a camera is a recorder."""
    _LOGGER.info(
        "%s reports the type of a camera but is a recorder: setting it up as an NVR",
        entry.runtime_data.host,
    )
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_RECORDER: True}
    )


READ_CAMERA: _Probe = (_get_settings, _get_values)
LIST_CHANNELS: _Probe = (_get_channels,)


def read_channel(channel: int) -> _Probe:
    """Return the probe of a camera attached to an NVR."""
    return (
        partial(_get_channel_settings, channel=channel),
        partial(_get_channel_values, channel=channel),
    )


@callback
def _async_retry_image_settings_later(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    probes: list[_Probe],
    client_args: tuple[Any, ...],
) -> None:
    """Try again, later, to read what the device did not give.

    The camera may only have been busy or restarting, and without this its image
    entities would be missing until the integration is reloaded by hand. Reloading
    stops the event stream and starts it again, and a camera that stays out of reach
    would do it every time: so what failed is read again, every few minutes, with a
    client of its own, and the entry is reloaded only once something can be read.
    One retry per entry; it goes with the entry, which an unload or a failed setup
    ends.
    """
    pending = list(probes)
    running = False
    data = entry.runtime_data

    def _stale() -> bool:
        """Return whether nothing more is wanted from the retry."""
        # A request would send a rejected password again, and a reload would cancel
        # the reauthentication that waits for a new one. A probe that ends after
        # the entry was unloaded, or once it began to unload, must not bring it back,
        # nor send the settings the entry no longer has.
        return (
            hass.is_stopping
            or entry.state is not ConfigEntryState.LOADED
            or _connection_settings(entry) != data.connection
            or getattr(entry, "runtime_data", None) is not data
            or data.stream_stop is not None
            or data.login_rejected
            or any(c.credentials_rejected for c in data.image_coordinators)
        )

    async def _async_close_unused(unused: ISAPIClient) -> None:
        """Close a client made for a retry that was cancelled meanwhile."""
        await async_run_to_end(hass, unused.close)

    def _step_unless_rejected(step: _Step, client: ISAPIClient) -> object:
        """Run a step, unless the password was rejected while it waited.

        A busy executor can start it late, after the check before it was handed over.
        """
        if data.login_rejected or any(
            c.credentials_rejected for c in data.image_coordinators
        ):
            raise _RetryRejected
        return step(client)

    async def _async_probe() -> None:
        nonlocal pending
        client = await async_run_to_end(
            hass, ISAPIClient, *client_args, on_result=_async_close_unused
        )
        try:
            recovered = False
            still_failing: list[_Probe] = []
            # Grows when a camera that was busy turns out to be a recorder.
            queue = list(pending)
            for probe in queue:
                for step in probe:
                    if _stale():
                        pending = []
                        return
                    try:
                        found = await async_run_to_end(
                            hass, _step_unless_rejected, step, client
                        )
                    except _RetryRejected:
                        pending = []
                        return
                    except ISAPIAuthError as err:
                        if err.status_code == 401:
                            pending = []
                            if not _stale():
                                await async_complete(_async_login_rejected(hass, entry))
                            return
                        # It does not allow it, and will not change its mind.
                        break
                    except ISAPIError as err:
                        if probe is READ_CAMERA and LIST_CHANNELS not in queue:
                            # As the setup does: a recorder that reports a camera
                            # type answers the camera's endpoints with an error.
                            queue.append(LIST_CHANNELS)
                        if _may_work_later(err):
                            still_failing.append(probe)
                        break
                else:
                    if probe is LIST_CHANNELS and not data.is_nvr:
                        if not found:
                            # Not a recorder: the camera's error stands.
                            continue
                        if _stale():
                            # It may not be the same device any more.
                            pending = []
                            return
                        # As the setup does: set up again as an NVR at once.
                        _async_record_recorder(hass, entry)
                    recovered = True
            pending = [] if recovered else still_failing
            # The last probe took time: check again before reloading.
            if recovered and not _stale():
                hass.config_entries.async_schedule_reload(entry.entry_id)
        finally:
            await async_run_to_end(hass, client.close)

    @callback
    def _async_retry(_now: datetime) -> None:
        nonlocal running
        if not pending or running or _stale():
            return
        running = True

        async def _async_run() -> None:
            nonlocal running
            try:
                await _async_probe()
            finally:
                running = False

        entry.async_create_background_task(
            hass, _async_run(), f"{DOMAIN} image settings retry"
        )

    entry.async_on_unload(
        async_track_time_interval(hass, _async_retry, IMAGE_SETTINGS_RETRY_INTERVAL)
    )


async def async_unload_entry(hass: HomeAssistant, entry: HikvisionConfigEntry) -> None:
    """Unload a config entry.

    One operation, run to its end even if the unload is cancelled meanwhile: the
    client must not stay open once its platforms are gone, and Home Assistant only
    finishes an unload that returns or raises an Exception. A CancelledError would
    leave the entry unloading, unable to load again, until a restart. So once it is
    cancelled, the unload reports what the operation did.
    """
    coordinators = list(entry.runtime_data.image_coordinators)
    for coordinator in coordinators:
        # Before the first await: a request that ends while the platforms unload must
        # not start reauthentication. Not a shutdown yet, as the unload can fail and
        # leave the entry loaded, polling.
        coordinator.unloading = True

    async def _async_unload_failed() -> None:
        """Deal with what the unload deferred, the entry staying loaded."""
        _async_ask_for_a_restart(hass, entry)
        for coordinator in coordinators:
            # Without hiding why the unload failed.
            try:
                await coordinator.async_unload_failed()
            except Exception:
                _LOGGER.exception(
                    "Error while resuming %s after a failed unload", entry.title
                )

    unload_error: BaseException | None = None

    async def _async_unload() -> None:
        nonlocal unload_error
        try:
            await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
            # Now that the platforms are gone, each step even if the one before
            # failed.
            try:
                # Unless a rejected password stopped it already.
                await async_stop_stream(hass, entry.runtime_data)
            finally:
                # Stop the polling, then wait for a request that is still running
                # before the client is closed under it. A request queued after that
                # is refused.
                await _async_close_image_settings(entry.runtime_data)
        except BaseException as err:
            # Home Assistant marks the entry as failed to unload, until a restart;
            # what the unload deferred is dealt with meanwhile.
            unload_error = err
            await _async_unload_failed()
            raise

    try:
        await async_complete(_async_unload())
    except asyncio.CancelledError:
        if unload_error is None:
            # The platforms are gone, the stream stopped and the client closed.
            return
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="unload_failed"
        ) from unload_error


def _connection_settings(entry: HikvisionConfigEntry) -> dict[str, object]:
    """Return the settings of the entry that a setup connects with."""
    return {
        key: entry.data.get(key)
        for key in (
            CONF_HOST,
            CONF_PORT,
            CONF_USERNAME,
            CONF_PASSWORD,
            CONF_SSL,
            CONF_VERIFY_SSL,
        )
    }


@callback
def _async_ask_for_a_restart(hass: HomeAssistant, entry: HikvisionConfigEntry) -> None:
    """Tell the user to restart, if saved settings wait for an unload that failed.

    A flow saves the new credentials or connection settings, then reloads the
    entry: if its unload fails, the entry cannot be loaded again with them until a
    restart, and the flow that saved them already said it worked.
    """
    if _connection_settings(entry) == entry.runtime_data.connection:
        return
    # Not persistent: the restart it asks for clears it.
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"restart_required_{entry.entry_id}",
        config_entry_id=entry.entry_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="restart_required",
        translation_placeholders={"name": entry.title},
    )
