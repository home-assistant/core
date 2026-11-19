"""The Hikvision integration."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import Any
from xml.etree.ElementTree import ParseError

from pyhik.constants import SENSOR_MAP
from pyhik.hikvision import HikCamera, VideoChannel, get_video_channels
from pyhik.isapi import (
    ISAPIAuthError,
    ISAPIClient,
    ISAPIConnectionError,
    ISAPIError,
    ISAPINotSupportedError,
)
import requests

from homeassistant.config_entries import ConfigEntry
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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .coordinator import (
    HikvisionImageCoordinator,
    async_reject_credentials,
    async_run_alone,
    entry_is_current,
)

_LOGGER = logging.getLogger(__name__)

# How long to wait before trying the image settings again after a failed read
IMAGE_SETTINGS_RETRY_INTERVAL = timedelta(minutes=5)

# What reads again a part of the image settings that could not be read: the requests
# to make one after the other, each with the client that is given to it. They are
# separate so that nothing is sent once the password is known to be refused.
type _Probe = tuple[Callable[[ISAPIClient], object], ...]

# What the callback that watches the credentials is registered for. The sensors
# register for their own IDs, and pyHik calls every callback when the stream
# changes state.
STREAM_CREDENTIALS_ID = "stream_credentials"

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
    device_id: str
    device_name: str
    device_type: str
    host: str
    username: str
    password: str
    channels: dict[int, VideoChannel] = field(default_factory=dict)
    # The client of the image settings, shared by all the coordinators: a
    # standalone camera has one coordinator, an NVR one per attached camera.
    image_client: ISAPIClient | None = None
    image_coordinators: list[HikvisionImageCoordinator] = field(default_factory=list)
    # Set when the device rejected the password, so that no coordinator sends it again
    image_credentials_rejected: bool = False


type HikvisionConfigEntry = ConfigEntry[HikvisionData]


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

    device_id = camera.get_id
    if device_id is None:
        if camera.auth_failed:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            )
        raise ConfigEntryNotReady(f"Unable to get device ID from {host}")

    device_name = camera.get_name or host
    device_type = camera.get_type or "Camera"

    # For NVRs, fetch video channel information
    channels: dict[int, VideoChannel] = {}
    if device_type == "NVR":
        channel_list = await hass.async_add_executor_job(
            get_video_channels, host, port, username, password, ssl, verify_ssl
        )
        channels = {ch.id: ch for ch in channel_list}
        _LOGGER.debug("Found %d video channels", len(channels))

    entry.runtime_data = HikvisionData(
        camera=camera,
        device_id=device_id,
        device_name=device_name,
        device_type=device_type,
        host=host,
        username=username,
        password=password,
        channels=channels,
    )

    _LOGGER.debug(
        "Device %s (type=%s) initial event_states: %s",
        device_name,
        device_type,
        camera.current_event_states,
    )

    # For NVRs or devices with no detected events, try to fetch events from ISAPI
    # Use broader notification methods for NVRs since they often use 'record' etc.
    if device_type == "NVR" or not camera.current_event_states:
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
        await hass.async_add_executor_job(camera.disconnect)

    # pyHik's stream thread is non-daemonic and publishes straight into hass, so
    # it has to be joined before the event loop closes. Starting it yields, so
    # the stop event may already have been fired by the time we get here, and
    # listening for it now would never hear it.
    if hass.is_stopping:
        await hass.async_add_executor_job(camera.disconnect)
        raise ConfigEntryNotReady("Home Assistant is stopping")

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_stream)
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

    # Without waiting for the image settings: the stream is already running, and
    # an event that arrives before its entities exist would be lost.
    event_platforms = [p for p in PLATFORMS if p in EVENT_PLATFORMS]
    image_platforms = [p for p in PLATFORMS if p not in EVENT_PLATFORMS]
    await hass.config_entries.async_forward_entry_setups(entry, event_platforms)

    try:
        (
            entry.runtime_data.image_client,
            entry.runtime_data.image_coordinators,
        ) = await _async_setup_image_settings(
            hass,
            entry,
            host,
            port,
            username,
            password,
            ssl,
            verify_ssl,
            device_type == "NVR",
        )

        if image_platforms:
            await hass.config_entries.async_forward_entry_setups(entry, image_platforms)

        _async_watch_stream_credentials(hass, entry)
    except BaseException as err:
        # A setup that fails, or is cancelled, does not call async_unload_entry, so
        # what it started is stopped here: the platforms it forwarded...
        await hass.config_entries.async_unload_platforms(entry, event_platforms)
        # ...the polling of the image settings (the client is closed by the
        # unload callback the image settings registered)...
        for coordinator in entry.runtime_data.image_coordinators:
            await coordinator.async_shutdown()
        # ...and the thread of the stream, which would keep the process from
        # ending. A rejected password stopped it before this was raised.
        if not isinstance(err, ConfigEntryAuthFailed):
            await hass.async_add_executor_job(camera.disconnect)
        raise


@callback
def _async_watch_stream_credentials(
    hass: HomeAssistant, entry: HikvisionConfigEntry
) -> None:
    """Ask for new credentials when the event stream is refused them.

    The stream is the only thing that talks to every device all the time, so it is
    the first to notice a changed password, including on a device with no image
    settings. pyHik slows the stream down when it happens, so that the account is
    not locked by retries, and calls the callbacks of the camera. It does not give
    up, so the stream is stopped here: the entry is reloaded, with a new stream, once
    the user has entered the new credentials.
    """
    data = entry.runtime_data
    camera = data.camera

    @callback
    def _async_handle() -> None:
        # This was queued by the thread of the stream: the entry may have been
        # unloaded, or reloaded, since, and must not be acted on by an old stream.
        if not entry_is_current(entry, data):
            return
        # pyHik calls the callbacks at every change of the stream: this does nothing
        # if the rejection is already being dealt with.
        entry.async_create_task(
            hass, async_reject_credentials(hass, entry), "hikvision stream credentials"
        )

    def _stream_changed(_msg: str) -> None:
        """Check the stream, from the thread of the stream."""
        if camera.stream_auth_failed:
            hass.loop.call_soon_threadsafe(_async_handle)

    camera.add_update_callback(_stream_changed, STREAM_CREDENTIALS_ID)
    entry.async_on_unload(
        partial(camera.remove_update_callback, _stream_changed, STREAM_CREDENTIALS_ID)
    )
    if camera.stream_auth_failed:
        # It was refused before this was registered.
        _async_handle()


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
) -> tuple[ISAPIClient | None, list[HikvisionImageCoordinator]]:
    """Discover the image settings of a camera, or of the cameras of an NVR.

    Image settings are an optional extra: a device that does not offer them, or
    does not allow reading them, simply gets no image entities.
    """
    client = await hass.async_add_executor_job(
        ISAPIClient, host, port, username, password, ssl, verify_ssl
    )
    lock = asyncio.Lock()
    closed = False

    async def _async_close() -> None:
        """Close the client once no request is using it."""
        nonlocal closed
        async with lock:
            if not closed:
                closed = True
                await hass.async_add_executor_job(client.close)

    # Not only at the end of the setup: a setup that fails, or is cancelled, runs
    # this too, and unloading the entry does as well.
    entry.async_on_unload(_async_close)
    retries: list[_Probe] = []
    if is_nvr:
        coordinators = await _async_setup_nvr_image_settings(
            hass, entry, client, lock, retries, quiet=False
        )
    else:
        coordinators = await _async_setup_camera_image_settings(
            hass, entry, client, lock, retries
        )
    if retries:
        _async_retry_image_settings_later(
            hass, entry, retries, (host, port, username, password, ssl, verify_ssl)
        )
    if not coordinators:
        await _async_close()
        return None, []
    return client, coordinators


async def _async_setup_camera_image_settings(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    client: ISAPIClient,
    lock: asyncio.Lock,
    retries: list[_Probe],
) -> list[HikvisionImageCoordinator]:
    """Discover the image settings of a standalone camera.

    What fails and may work later is added to ``retries``.
    """
    host = entry.data[CONF_HOST]
    try:
        settings = await async_run_alone(hass, entry, lock, client.get_image_settings)
    except ISAPIAuthError as err:
        if err.status_code == 401:
            raise await _async_credentials_rejected(hass, entry) from err
        _LOGGER.warning("Not allowed to read the image settings of %s: %s", host, err)
        return []
    except ISAPIConnectionError as err:
        _LOGGER.warning("Unable to read the image settings of %s: %s", host, err)
        retries.append(_READ_CAMERA)
        return []
    except ISAPIError as err:
        # Some recorders report the type of a camera, so the device type cannot
        # tell them apart. They answer the camera's endpoints with an error, but
        # the cameras attached to them are reachable through the NVR's.
        if coordinators := await _async_setup_nvr_image_settings(
            hass, entry, client, lock, retries, quiet=True
        ):
            _LOGGER.debug(
                "%s is a recorder: reading the image settings of its cameras", host
            )
            return coordinators
        if isinstance(err, ISAPINotSupportedError):
            _LOGGER.debug("%s does not support image settings", host)
        else:
            _LOGGER.warning("Unable to read the image settings of %s: %s", host, err)
            if _is_server_busy(err):
                retries.append(_READ_CAMERA)
        return []

    coordinator = HikvisionImageCoordinator(hass, entry, client, settings, lock=lock)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        # The events work without the image settings, so do not hold them back.
        _LOGGER.warning("Unable to read the image values of %s: %s", host, err)
        if _may_work_later(err):
            retries.append(_READ_CAMERA)
        return []
    return [coordinator]


async def _async_setup_nvr_image_settings(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    client: ISAPIClient,
    lock: asyncio.Lock,
    retries: list[_Probe],
    *,
    quiet: bool,
) -> list[HikvisionImageCoordinator]:
    """Discover the image settings of the cameras attached to an NVR.

    The cameras are read through the NVR's proxy endpoints, with the channel IDs
    the NVR lists. With ``quiet`` a failure to list them is only logged for
    debugging, because the device may simply not be an NVR. What fails and may work
    later is added to ``retries``.
    """
    host = entry.data[CONF_HOST]
    try:
        image_channels = await async_run_alone(
            hass, entry, lock, partial(client.get_image_channels, proxy=True)
        )
    except ISAPIError as err:
        if isinstance(err, ISAPIAuthError) and err.status_code == 401:
            raise await _async_credentials_rejected(hass, entry) from err
        if isinstance(err, ISAPIConnectionError) or _is_server_busy(err):
            retries.append(_LIST_CHANNELS)
        if quiet or isinstance(err, ISAPINotSupportedError):
            _LOGGER.debug("%s does not list image channels: %s", host, err)
        elif isinstance(err, ISAPIAuthError):
            _LOGGER.warning(
                "Not allowed to read the image settings of %s: %s", host, err
            )
        else:
            _LOGGER.warning("Unable to read the image settings of %s: %s", host, err)
        return []

    coordinators: list[HikvisionImageCoordinator] = []
    for image_channel in image_channels:
        if image_channel.enabled is False:
            continue
        channel = image_channel.id
        try:
            settings = await async_run_alone(
                hass,
                entry,
                lock,
                partial(client.get_image_settings, channel, proxy=True),
            )
        except ISAPINotSupportedError:
            # The NVR may list a camera that it cannot proxy.
            _LOGGER.debug("Channel %s of %s has no image settings", channel, host)
            continue
        except ISAPIError as err:
            if isinstance(err, ISAPIAuthError) and err.status_code == 401:
                raise await _async_credentials_rejected(hass, entry) from err
            _LOGGER.warning(
                "Unable to read the image settings of channel %s of %s: %s",
                channel,
                host,
                err,
            )
            if isinstance(err, ISAPIConnectionError) or _is_server_busy(err):
                retries.append(_read_channel(channel))
            continue
        coordinator = HikvisionImageCoordinator(
            hass, entry, client, settings, channel, lock
        )
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady as err:
            _LOGGER.warning(
                "Unable to read the image values of channel %s of %s: %s",
                channel,
                host,
                err,
            )
            if _may_work_later(err):
                retries.append(_read_channel(channel))
            continue
        coordinators.append(coordinator)
    return coordinators


async def _async_credentials_rejected(
    hass: HomeAssistant, entry: HikvisionConfigEntry
) -> ConfigEntryAuthFailed:
    """Stop the event stream and return the error that asks for new credentials.

    The device rejects the credentials, not just one request. The event stream
    would keep using them, which can lock the account.
    """
    await hass.async_add_executor_job(entry.runtime_data.camera.disconnect)
    return ConfigEntryAuthFailed(
        translation_domain=DOMAIN, translation_key="invalid_auth"
    )


def _is_server_busy(err: ISAPIError) -> bool:
    """Return whether the device answered that it cannot serve the request now.

    A server error such as an HTTP 500 or 503 is how a busy camera answers. Any
    other error that is not a connection error is not expected to go away.
    """
    return (
        not isinstance(err, ISAPINotSupportedError)
        and err.status_code is not None
        and err.status_code >= 500
    )


def _may_work_later(err: BaseException) -> bool:
    """Return whether a failed read may work if it is tried again later.

    The first refresh wraps the error of the camera. A camera that does not allow
    the read, or does not have the endpoint, will not change its mind.
    """
    cause: BaseException | None = err
    while cause is not None:
        if isinstance(cause, (ISAPIAuthError, ISAPINotSupportedError)):
            return False
        cause = cause.__cause__
    return True


def _get_settings(client: ISAPIClient) -> None:
    """Read the image settings of a standalone camera."""
    client.get_image_settings()


def _get_values(client: ISAPIClient) -> None:
    """Read the image values of a standalone camera."""
    client.get_image_values()


def _get_channels(client: ISAPIClient) -> None:
    """List the image channels of an NVR."""
    client.get_image_channels(proxy=True)


def _get_channel_settings(client: ISAPIClient, channel: int) -> None:
    """Read the image settings of a camera attached to an NVR."""
    client.get_image_settings(channel, proxy=True)


def _get_channel_values(client: ISAPIClient, channel: int) -> None:
    """Read the image values of a camera attached to an NVR."""
    client.get_image_values(channel, proxy=True)


_READ_CAMERA: _Probe = (_get_settings, _get_values)
_LIST_CHANNELS: _Probe = (_get_channels,)


def _read_channel(channel: int) -> _Probe:
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
    would do it every time. So it is read again with a client of its own, and the
    entry is reloaded only when something can be read.
    """
    pending = list(probes)
    running = False
    # What this setup started must not act on another one: Home Assistant waits only
    # a few seconds for the tasks of an entry, so a slow probe can end after a reload.
    data = entry.runtime_data

    def _stale() -> bool:
        """Return whether nothing more is wanted from this probe."""
        # A request would send a rejected password again, and a reload would cancel
        # the reauthentication that waits for a new one. A probe that was running
        # when the entry was unloaded must not bring it back.
        return not entry_is_current(entry, data) or data.image_credentials_rejected

    async def _async_probe() -> None:
        nonlocal pending, running
        running = True
        client = await hass.async_add_executor_job(ISAPIClient, *client_args)
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
                        await hass.async_add_executor_job(step, client)
                    except ISAPIAuthError as err:
                        if err.status_code == 401:
                            pending = []
                            if _stale():
                                # The probe outlived its setup: the refusal is of
                                # the password of that one.
                                return
                            # The camera refuses the password: everything that
                            # would send it again is stopped, and new credentials
                            # are asked for.
                            await async_reject_credentials(hass, entry)
                            return
                        # It does not allow it, and will not change its mind.
                        break
                    except ISAPINotSupportedError:
                        if probe is _READ_CAMERA and _LIST_CHANNELS not in queue:
                            # Not a camera: a recorder has its channels to list, as
                            # setup does when the camera endpoint is not there.
                            queue.append(_LIST_CHANNELS)
                        break
                    except ISAPIError as err:
                        if (
                            probe is _READ_CAMERA
                            and not isinstance(err, ISAPIConnectionError)
                            and _LIST_CHANNELS not in queue
                        ):
                            # Setup falls back to the recorder endpoints on any
                            # error of the camera's, and so does this.
                            queue.append(_LIST_CHANNELS)
                        if isinstance(err, ISAPIConnectionError) or _is_server_busy(
                            err
                        ):
                            still_failing.append(probe)
                        break
                else:
                    recovered = True
            if recovered:
                pending = []
                # The last probe took time: the password may have been refused, or
                # the entry unloaded, in the meantime.
                if not _stale():
                    hass.config_entries.async_schedule_reload(entry.entry_id)
            else:
                pending = still_failing
        finally:
            running = False
            await hass.async_add_executor_job(client.close)

    @callback
    def _retry(_now: datetime) -> None:
        if pending and not running:
            entry.async_create_task(
                hass, _async_probe(), "hikvision image settings retry"
            )

    entry.async_on_unload(
        async_track_time_interval(hass, _retry, IMAGE_SETTINGS_RETRY_INTERVAL)
    )


async def async_unload_entry(hass: HomeAssistant, entry: HikvisionConfigEntry) -> None:
    """Unload a config entry."""
    data = entry.runtime_data
    for coordinator in data.image_coordinators:
        # Before anything is awaited: what is waiting for the client must not use it
        # while the platforms unload, and a request that ends in the meantime must
        # not be taken for one of a setup that is still wanted.
        coordinator.closed = True
    try:
        await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    except BaseException:
        # The entry stays loaded.
        for coordinator in data.image_coordinators:
            coordinator.closed = False
        raise
    # Stop the event stream
    await hass.async_add_executor_job(data.camera.disconnect)
    for coordinator in data.image_coordinators:
        await coordinator.async_shutdown()
    if data.image_coordinators:
        # Home Assistant waits only a few seconds for the tasks of an entry, and
        # deletes the runtime data after that: a request that is running has to
        # end here, and nothing queued starts after it.
        async with data.image_coordinators[0].lock:
            pass
    # The client is closed after this, once the request that is running has ended.
