"""The Hikvision integration."""

from dataclasses import dataclass, field
import logging
from xml.etree.ElementTree import ParseError

from pyhik.constants import SENSOR_MAP
from pyhik.hikvision import HikCamera, VideoChannel, get_video_channels
from pyhik.isapi import ISAPIAuthError, ISAPIClient, ISAPIError, ISAPINotSupportedError
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
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import HikvisionImageCoordinator

_LOGGER = logging.getLogger(__name__)

# What the event stream feeds. These are set up before the image settings are
# read: a camera that is slow to answer must not hold back the events of its stream.
EVENT_PLATFORMS = [Platform.BINARY_SENSOR, Platform.CAMERA, Platform.EVENT]
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.EVENT,
    Platform.NUMBER,
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
    image_coordinator: HikvisionImageCoordinator | None = None


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
        # Image settings are only read from standalone cameras.
        if device_type != "NVR":
            entry.runtime_data.image_coordinator = await _async_setup_image_settings(
                hass, entry, host, port, username, password, ssl, verify_ssl
            )

        if image_platforms:
            await hass.config_entries.async_forward_entry_setups(entry, image_platforms)
    except BaseException as err:
        # A setup that fails, or is cancelled, does not call async_unload_entry, so
        # what it started is stopped here: the platforms it forwarded...
        await hass.config_entries.async_unload_platforms(entry, event_platforms)
        # ...the image settings client, if the image platforms failed after it...
        if coordinator := entry.runtime_data.image_coordinator:
            await coordinator.async_shutdown()
            await hass.async_add_executor_job(coordinator.client.close)
        # ...and the thread of the stream, which would keep the process from
        # ending. A rejected password stopped it before this was raised.
        if not isinstance(err, ConfigEntryAuthFailed):
            await hass.async_add_executor_job(camera.disconnect)
        raise


def _close_client_and_stream(client: ISAPIClient, camera: HikCamera) -> None:
    """Close the image settings client and stop the event stream."""
    client.close()
    camera.disconnect()


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
    client = await hass.async_add_executor_job(
        ISAPIClient, host, port, username, password, ssl, verify_ssl
    )
    try:
        return await _async_discover_image_settings(hass, entry, host, client)
    except ConfigEntryAuthFailed:
        # The client was closed before this was raised.
        raise
    except BaseException:
        # Anything unexpected, or a cancelled setup, must not leave it open.
        await hass.async_add_executor_job(client.close)
        raise


async def _async_discover_image_settings(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    host: str,
    client: ISAPIClient,
) -> HikvisionImageCoordinator | None:
    """Read the image settings with the client, and close it if there are none."""
    try:
        settings = await hass.async_add_executor_job(client.get_image_settings)
    except ISAPINotSupportedError:
        _LOGGER.debug("%s does not support image settings", host)
    except ISAPIAuthError as err:
        if err.status_code == 401:
            # The device rejects the credentials, not just this request. The event
            # stream would keep using them, so stop it before asking for new ones.
            await hass.async_add_executor_job(
                _close_client_and_stream, client, entry.runtime_data.camera
            )
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        _LOGGER.warning("Not allowed to read the image settings of %s: %s", host, err)
    except ISAPIError as err:
        _LOGGER.warning("Unable to read the image settings of %s: %s", host, err)
    else:
        coordinator = HikvisionImageCoordinator(hass, entry, client, settings)
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady as err:
            # The events work without the image settings, so do not hold them back.
            _LOGGER.warning("Unable to read the image values of %s: %s", host, err)
        except ConfigEntryAuthFailed:
            await hass.async_add_executor_job(client.close)
            raise
        else:
            return coordinator
    await hass.async_add_executor_job(client.close)
    return None


async def async_unload_entry(hass: HomeAssistant, entry: HikvisionConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    # Stop the event stream
    await hass.async_add_executor_job(entry.runtime_data.camera.disconnect)
    if coordinator := entry.runtime_data.image_coordinator:
        # Stop the polling, then wait for a request that is still running before the
        # client is closed under it.
        await coordinator.async_shutdown()
        async with coordinator.lock:
            await hass.async_add_executor_job(coordinator.client.close)
