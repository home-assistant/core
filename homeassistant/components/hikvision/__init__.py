"""The Hikvision integration."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import uuid
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
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_call_later

from .const import CONF_RANDOM_ID, DOMAIN
from .coordinator import (
    HikvisionImageCoordinator,
    async_complete,
    async_run_to_end,
    async_stop_stream,
)
from .identity import is_made_up_id, is_random_id_made_up, looks_made_up

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
    host: str
    username: str
    password: str
    channels: dict[int, VideoChannel] = field(default_factory=dict)
    image_coordinator: HikvisionImageCoordinator | None = None
    # The stop of the event stream, shared by everything that stops it
    stream_stop: asyncio.Task[None] | None = None


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
    if CONF_RANDOM_ID in entry.data or entry.unique_id is None:
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


def _made_up_prefix(identifier: str, device_id: str) -> tuple[str, str] | None:
    """Split an identifier made with another made-up ID into that ID and the rest.

    The unique IDs and device identifiers start with the device's ID, then "_" and
    the rest, if any. A UUID has no "_" in it.
    """
    old_id, separator, rest = identifier.partition("_")
    if old_id == device_id or not looks_made_up(old_id):
        return None
    return old_id, separator + rest


@callback
def _async_adopt_made_up_identities(
    hass: HomeAssistant, entry: HikvisionConfigEntry, device_id: str
) -> None:
    """Move the devices and entities of earlier made-up IDs to the entry's own ID.

    Before the entry kept its ID, each setup registered them under the random ID
    pyHik made up on that connection, which differs from the one the entry was
    created with. The oldest of each is kept: it has the entity ID automations
    use. One the entry's ID already has is left as it is.
    """
    dev_reg = dr.async_get(hass)
    devices = sorted(
        dr.async_entries_for_config_entry(dev_reg, entry.entry_id),
        key=lambda device: device.created_at,
    )
    # The identifiers of the entry's devices, channel devices included.
    taken = {identifier for device in devices for identifier in device.identifiers}
    for device in devices:
        identifiers = set(device.identifiers)
        for domain, identifier in device.identifiers:
            if domain != DOMAIN or not (
                split := _made_up_prefix(identifier, device_id)
            ):
                continue
            new_identifier = (DOMAIN, device_id + split[1])
            if new_identifier not in taken:
                identifiers.discard((domain, identifier))
                identifiers.add(new_identifier)
                taken.add(new_identifier)
        if identifiers != device.identifiers:
            dev_reg.async_update_device(device.id, new_identifiers=identifiers)

    ent_reg = er.async_get(hass)
    for entity in sorted(
        er.async_entries_for_config_entry(ent_reg, entry.entry_id),
        key=lambda entity: entity.created_at,
    ):
        if not (split := _made_up_prefix(entity.unique_id, device_id)):
            continue
        new_unique_id = device_id + split[1]
        if ent_reg.async_get_entity_id(entity.domain, DOMAIN, new_unique_id) is None:
            ent_reg.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)


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
    if isinstance(camera_id, uuid.UUID) and is_made_up_id(entry):
        # pyHik before 0.5.1 makes up a random ID for a device whose own ID is too
        # short, a new one at every connection. An entry created with such an ID
        # keeps it, so its device and entities stay the same. An entry with a real
        # or derived ID does not lend it: a camera that answers with a made-up ID
        # is not known to be the one it was created for.
        device_id = str(entry.unique_id)
        _async_adopt_made_up_identities(hass, entry, device_id)

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
        stream_id=stream_id,
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
        await async_stop_stream(hass, entry.runtime_data)

    # pyHik's stream thread is non-daemonic and publishes straight into hass, so
    # it has to be joined before the event loop closes. Starting it yields, so
    # the stop event may already have been fired by the time we get here, and
    # listening for it now would never hear it.
    if hass.is_stopping:
        await async_stop_stream(hass, entry.runtime_data)
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
    # Every platform whose setup was started: a setup that is cancelled, or fails,
    # halfway through forwarding can leave some of them set up.
    forwarded = list(event_platforms)

    try:
        await hass.config_entries.async_forward_entry_setups(entry, event_platforms)

        # Image settings are only read from standalone cameras.
        if device_type != "NVR":
            entry.runtime_data.image_coordinator = await _async_setup_image_settings(
                hass, entry, host, port, username, password, ssl, verify_ssl
            )

        if image_platforms:
            forwarded.extend(image_platforms)
            await hass.config_entries.async_forward_entry_setups(entry, image_platforms)
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
                    if coordinator := entry.runtime_data.image_coordinator:
                        await coordinator.async_close()
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


async def _async_setup_image_settings(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    host: str,
    port: int,
    username: str,
    password: str,
    ssl: bool,
    verify_ssl: bool,
) -> HikvisionImageCoordinator | None:
    """Discover the image settings of a camera.

    Image settings are an optional extra: a camera that does not offer them, or
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
    closed = False

    async def _async_close() -> None:
        """Close the client, once and to its end, whatever path asks first."""
        nonlocal closed
        if closed:
            return

        async def _async_close_now() -> None:
            nonlocal closed
            await async_run_to_end(hass, client.close)
            closed = True

        try:
            await async_complete(_async_close_now())
        except Exception:
            # Why the client is closed (no image settings, a rejected password, a
            # failed setup) matters more than the close: it is not replaced. Not
            # marked closed, so a later path can try again.
            _LOGGER.exception("Error closing the image settings client of %s", host)

    try:
        return await _async_discover_image_settings(
            hass, entry, host, client, _async_close
        )
    except BaseException:
        # Anything unexpected, or a cancelled setup, must not leave it open. Not
        # closed twice: a path that already closed it is not repeated.
        await _async_close()
        raise


async def _async_discover_image_settings(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    host: str,
    client: ISAPIClient,
    close: Callable[[], Awaitable[None]],
) -> HikvisionImageCoordinator | None:
    """Read the image settings with the client, and close it if there are none."""
    try:
        # To its end even if the setup is cancelled: the client is closed after it.
        settings = await async_run_to_end(hass, client.get_image_settings)
    except ISAPINotSupportedError:
        _LOGGER.debug("%s does not support image settings", host)
    except ISAPIAuthError as err:
        if err.status_code == 401:
            # The device rejects the credentials, not just this request. The event
            # stream would keep using them, so stop it before asking for new ones.
            await close()
            try:
                await async_stop_stream(hass, entry.runtime_data)
            except Exception:
                # Still ask for new credentials: the clean-up of the failed setup
                # tries to stop the stream again.
                _LOGGER.exception("Error stopping the event stream of %s", host)
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        _LOGGER.warning("Not allowed to read the image settings of %s: %s", host, err)
    except ISAPIError as err:
        _LOGGER.warning("Unable to read the image settings of %s: %s", host, err)
        if _may_work_later(err):
            _async_retry_image_settings_later(hass, entry)
    else:
        coordinator = HikvisionImageCoordinator(hass, entry, client, settings)
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady as err:
            # The events work without the image settings, so do not hold them back.
            _LOGGER.warning("Unable to read the image values of %s: %s", host, err)
            if _may_work_later(err):
                _async_retry_image_settings_later(hass, entry)
        except ConfigEntryAuthFailed:
            await close()
            raise
        else:
            return coordinator
    await close()
    return None


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


def _async_retry_image_settings_later(
    hass: HomeAssistant, entry: HikvisionConfigEntry
) -> None:
    """Try the image settings again later, by reloading the entry.

    The camera may only have been busy or restarting, and without this its image
    entities would be missing until the integration is reloaded by hand. The
    timer goes with the entry: an unload, or a failed setup, cancels it.
    """

    @callback
    def _reload(_now: datetime) -> None:
        if not hass.is_stopping:
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_call_later(hass, IMAGE_SETTINGS_RETRY_INTERVAL, _reload)
    )


async def async_unload_entry(hass: HomeAssistant, entry: HikvisionConfigEntry) -> None:
    """Unload a config entry."""
    coordinator = entry.runtime_data.image_coordinator
    if coordinator is not None:
        # Before the first await: a request that ends while the platforms unload must
        # not start reauthentication. Not a shutdown yet, as the unload can fail and
        # leave the entry loaded, polling.
        coordinator.unloading = True

    async def _async_unload_failed() -> None:
        """Deal with what the unload deferred, the entry staying loaded."""
        if coordinator is None:
            return
        # Without hiding why the unload failed.
        try:
            await coordinator.async_unload_failed()
        except Exception:
            _LOGGER.exception(
                "Error while resuming %s after a failed unload", entry.title
            )

    try:
        await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    except BaseException:
        await _async_unload_failed()
        raise

    release_failed = False

    async def _async_release() -> None:
        """Stop the stream and close the client, now that the platforms are gone."""
        nonlocal release_failed
        try:
            try:
                # Unless a rejected password stopped it already.
                await async_stop_stream(hass, entry.runtime_data)
            finally:
                if coordinator is not None:
                    # Stop the polling, then wait for a request that is still
                    # running before the client is closed under it. A request
                    # queued after that is refused.
                    await coordinator.async_close()
        except BaseException:
            release_failed = True
            raise

    try:
        # One operation, to its end even if the unload is cancelled meanwhile: the
        # client must not stay open once its platforms are gone.
        await async_complete(_async_release())
    except Exception:
        # The stream could not be stopped: the entry stays loaded.
        await _async_unload_failed()
        raise
    except asyncio.CancelledError:
        # The release ran to its end all the same. Only if it failed does the entry
        # stay loaded, with what the unload deferred still to deal with; after one
        # that worked, the stream is stopped and the client closed.
        if release_failed:
            await async_complete(_async_unload_failed())
        raise
