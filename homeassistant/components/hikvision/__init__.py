"""The Hikvision integration."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
import logging
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
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN
from .coordinator import HikvisionImageCoordinator

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
    if is_nvr:
        coordinators = await _async_setup_nvr_image_settings(
            hass, entry, client, lock, quiet=False
        )
    else:
        coordinators = await _async_setup_camera_image_settings(
            hass, entry, client, lock
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
) -> list[HikvisionImageCoordinator]:
    """Discover the image settings of a standalone camera."""
    host = entry.data[CONF_HOST]
    try:
        settings = await hass.async_add_executor_job(client.get_image_settings)
    except ISAPIAuthError as err:
        if err.status_code == 401:
            raise await _async_credentials_rejected(hass, entry) from err
        _LOGGER.warning("Not allowed to read the image settings of %s: %s", host, err)
        return []
    except ISAPIConnectionError as err:
        _LOGGER.warning("Unable to read the image settings of %s: %s", host, err)
        _async_retry_image_settings_later(hass, entry)
        return []
    except ISAPIError as err:
        # Some recorders report the type of a camera, so the device type cannot
        # tell them apart. They answer the camera's endpoints with an error, but
        # the cameras attached to them are reachable through the NVR's.
        if coordinators := await _async_setup_nvr_image_settings(
            hass, entry, client, lock, quiet=True
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
                _async_retry_image_settings_later(hass, entry)
        return []

    coordinator = HikvisionImageCoordinator(hass, entry, client, settings, lock=lock)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        # The events work without the image settings, so do not hold them back.
        _LOGGER.warning("Unable to read the image values of %s: %s", host, err)
        if _may_work_later(err):
            _async_retry_image_settings_later(hass, entry)
        return []
    return [coordinator]


async def _async_setup_nvr_image_settings(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    client: ISAPIClient,
    lock: asyncio.Lock,
    *,
    quiet: bool,
) -> list[HikvisionImageCoordinator]:
    """Discover the image settings of the cameras attached to an NVR.

    The cameras are read through the NVR's proxy endpoints, with the channel IDs
    the NVR lists. With ``quiet`` a failure to list them is only logged for
    debugging, because the device may simply not be an NVR.
    """
    host = entry.data[CONF_HOST]
    try:
        image_channels = await hass.async_add_executor_job(
            partial(client.get_image_channels, proxy=True)
        )
    except ISAPIError as err:
        if isinstance(err, ISAPIAuthError) and err.status_code == 401:
            raise await _async_credentials_rejected(hass, entry) from err
        if isinstance(err, ISAPIConnectionError) or _is_server_busy(err):
            # Whether it is logged or not: the camera may only have been busy.
            _async_retry_image_settings_later(hass, entry)
        if quiet or isinstance(err, ISAPINotSupportedError):
            _LOGGER.debug("%s does not list image channels: %s", host, err)
        elif isinstance(err, ISAPIAuthError):
            _LOGGER.warning(
                "Not allowed to read the image settings of %s: %s", host, err
            )
        else:
            _LOGGER.warning("Unable to read the image settings of %s: %s", host, err)
        return []

    retry = False
    coordinators: list[HikvisionImageCoordinator] = []
    for image_channel in image_channels:
        if image_channel.enabled is False:
            continue
        channel = image_channel.id
        try:
            settings = await hass.async_add_executor_job(
                partial(client.get_image_settings, channel, proxy=True)
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
            retry = (
                retry or isinstance(err, ISAPIConnectionError) or _is_server_busy(err)
            )
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
            retry = retry or _may_work_later(err)
            continue
        coordinators.append(coordinator)
    if retry:
        _async_retry_image_settings_later(hass, entry)
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


def _async_retry_image_settings_later(
    hass: HomeAssistant, entry: HikvisionConfigEntry
) -> None:
    """Try the image settings again later, by reloading the entry.

    The camera may only have been busy or restarting, and without this its image
    entities would be missing until the integration is reloaded by hand.
    """

    @callback
    def _reload(_now: datetime) -> None:
        # A reload would send the rejected password again, and cancel the
        # reauthentication that is waiting for a new one.
        if entry.runtime_data.image_credentials_rejected:
            return
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_call_later(hass, IMAGE_SETTINGS_RETRY_INTERVAL, _reload)
    )


async def async_unload_entry(hass: HomeAssistant, entry: HikvisionConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    # Stop the event stream
    await hass.async_add_executor_job(entry.runtime_data.camera.disconnect)
    data = entry.runtime_data
    for coordinator in data.image_coordinators:
        await coordinator.async_shutdown()
    # The client is closed after this, once the request that is running has ended.
