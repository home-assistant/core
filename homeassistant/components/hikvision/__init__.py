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
from homeassistant.helpers.event import async_call_later

from .const import CONF_RANDOM_ID, DOMAIN
from .coordinator import (
    HikvisionImageCoordinator,
    async_complete,
    async_run_to_end,
    async_stop_stream,
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
    host: str
    username: str
    password: str
    channels: dict[int, VideoChannel] = field(default_factory=dict)
    image_coordinator: HikvisionImageCoordinator | None = None
    # The stop of the event stream, shared by everything that stops it
    stream_stop: asyncio.Task[None] | None = None
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

        # Image settings are only read from standalone cameras.
        if device_type != "NVR":
            entry.runtime_data.image_coordinator = await _async_setup_image_settings(
                hass, entry, host, port, username, password, ssl, verify_ssl
            )
            if hass.is_stopping:
                # The stop closed what it found before the discovery ended: the
                # client is closed here instead, and has no entities.
                await _async_close_image_settings(entry.runtime_data)
                entry.runtime_data.image_coordinator = None

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
    """Unload a config entry.

    One operation, run to its end even if the unload is cancelled meanwhile: the
    client must not stay open once its platforms are gone, and Home Assistant only
    finishes an unload that returns or raises an Exception. A CancelledError would
    leave the entry unloading, unable to load again, until a restart. So once it is
    cancelled, the unload reports what the operation did.
    """
    coordinator = entry.runtime_data.image_coordinator
    if coordinator is not None:
        # Before the first await: a request that ends while the platforms unload must
        # not start reauthentication. Not a shutdown yet, as the unload can fail and
        # leave the entry loaded, polling.
        coordinator.unloading = True

    async def _async_unload_failed() -> None:
        """Deal with what the unload deferred, the entry staying loaded."""
        _async_ask_for_a_restart(hass, entry)
        if coordinator is None:
            return
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


async def _async_close_image_settings(data: HikvisionData) -> None:
    """Stop the polling of the image settings, then close their client.

    The client is closed once no request is using it.
    """
    if (coordinator := data.image_coordinator) is not None:
        await coordinator.async_close()


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
