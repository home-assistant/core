"""Support for Nest devices."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Awaitable, Callable
from http import HTTPStatus
import logging
import os
import socket

from aiohttp import ClientError, ClientResponseError, web
from google_nest_sdm.camera_traits import CameraClipPreviewTrait
from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage
from google_nest_sdm.event_media import Media
from google_nest_sdm.exceptions import (
    ApiException,
    AuthException,
    ConfigurationException,
    SubscriberException,
)
from google_nest_sdm.traits import TraitType
import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components.camera import Image, img_util
from homeassistant.components.http import KEY_HASS_USER
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_MONITORED_CONDITIONS,
    CONF_SENSORS,
    CONF_STRUCTURE,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    Unauthorized,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.typing import ConfigType

from . import api
from .const import (
    CONF_PROJECT_ID,
    CONF_SUBSCRIBER_ID,
    DATA_SDM,
    DOMAIN,
)
from .events import EVENT_NAME_MAP, NEST_EVENT
from .media_source import (
    async_get_media_event_store,
    async_get_transcoder,
)
from .types import NestConfigEntry, NestData

_LOGGER = logging.getLogger(__name__)


def _test_ipv6_connectivity() -> bool:
    """
    Test IPv6 connectivity to Google services.

    Returns True if IPv6 connectivity is working, False if IPv4 preference should be used.
    This helps detect partial IPv6 configurations that cause subscriber timeouts.
    """
    try:
        # Test IPv6 connection to Google's public DNS
        # This mimics the connectivity that gRPC will attempt for Google Cloud services
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock.settimeout(3.0)  # Quick timeout to avoid delaying integration startup
        sock.connect(("2001:4860:4860::8888", 53))  # Google DNS IPv6
        sock.close()

        _LOGGER.debug("IPv6 connectivity test to Google services: PASSED")
        return True

    except (socket.error, OSError, TimeoutError) as e:
        _LOGGER.debug("IPv6 connectivity test to Google services failed: %s", e)
        return False
    except Exception as e:
        _LOGGER.debug("Unexpected error in IPv6 connectivity test: %s", e)
        return False


def _configure_ipv4_preference() -> None:
    """
    Configure IPv4 preference for Google Cloud gRPC connections.

    This function detects IPv6 network issues and forces Google Cloud libraries
    to prefer IPv4 connections, resolving "Timeout in streaming_pull" errors
    on systems with partial IPv6 configuration.

    Based on GitHub issue #139485 and related IPv6 network timeout issues.
    """
    # Check if IPv4 preference is already configured
    if os.environ.get("GRPC_PREFER_IPV4") == "1":
        _LOGGER.debug("IPv4 preference already configured for Google Cloud connections")
        return

    # Test IPv6 connectivity to Google services
    ipv6_working = _test_ipv6_connectivity()

    if not ipv6_working:
        _LOGGER.info(
            "IPv6 connectivity issues detected, enabling IPv4 preference for "
            "Google Cloud connections to prevent Nest subscriber timeouts. "
            "See: https://github.com/home-assistant/core/issues/139485"
        )

        # Configure gRPC environment variables to prefer IPv4 connections
        os.environ["GRPC_DNS_RESOLVER"] = "native"
        os.environ["GRPC_PREFER_IPV4"] = "1"
        os.environ["GRPC_VERBOSITY"] = "ERROR"  # Reduce gRPC logging noise

        _LOGGER.debug(
            "IPv4 preference configured: GRPC_DNS_RESOLVER=native, GRPC_PREFER_IPV4=1"
        )
    else:
        _LOGGER.debug(
            "IPv6 connectivity to Google services working correctly, "
            "using default gRPC network settings"
        )


SENSOR_SCHEMA = vol.Schema(
    {vol.Optional(CONF_MONITORED_CONDITIONS): vol.All(cv.ensure_list, [cv.string])}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_CLIENT_ID): cv.string,
                vol.Optional(CONF_CLIENT_SECRET): cv.string,
                vol.Optional(CONF_PROJECT_ID): cv.string,
                vol.Optional(CONF_SUBSCRIBER_ID): cv.string,
                vol.Optional(CONF_STRUCTURE): vol.All(cv.ensure_list, [cv.string]),
                vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
                vol.Optional(CONF_BINARY_SENSORS, default={}): SENSOR_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Platforms for SDM API
PLATFORMS = [Platform.CAMERA, Platform.CLIMATE, Platform.EVENT, Platform.SENSOR]

# Fetch media events with a disk backed cache, with a limit for each camera
# device. The largest media items are mp4 clips at ~450kb each, and we target
# ~125MB of storage per camera to try to balance a reasonable user experience
# for event history not not filling the disk.
EVENT_MEDIA_CACHE_SIZE = 256  # number of events

THUMBNAIL_SIZE_PX = 175


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Nest components with dispatch between old/new flows."""
    hass.http.register_view(NestEventMediaView(hass))
    hass.http.register_view(NestEventMediaThumbnailView(hass))
    return True


class SignalUpdateCallback:
    """An EventCallback invoked when new events arrive from subscriber."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_reload_cb: Callable[[], Awaitable[None]],
        config_entry: NestConfigEntry,
    ) -> None:
        """Initialize EventCallback."""
        self._hass = hass
        self._config_reload_cb = config_reload_cb
        self._config_entry = config_entry

    async def async_handle_event(self, event_message: EventMessage) -> None:
        """Process an incoming EventMessage."""
        if event_message.relation_update:
            _LOGGER.info("Devices or homes have changed; Need reload to take effect")
            return
        if not event_message.resource_update_name:
            return
        device_id = event_message.resource_update_name
        if not (events := event_message.resource_update_events):
            return
        _LOGGER.debug("Event Update %s", events.keys())
        device_registry = dr.async_get(self._hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, device_id)}
        )
        if not device_entry:
            return

        for event in events.values():
            event_type = EVENT_NAME_MAP.get(type(event))
            if event_type is None:
                continue

            message = {
                "device_id": device_entry.id,
                "type": event_type,
            }
            if hasattr(event, "timestamp"):
                message["timestamp"] = event.timestamp.isoformat()
            if hasattr(event, "nest_event_id"):
                message["nest_event_id"] = event.nest_event_id
            if hasattr(event, "zones"):
                message["zones"] = event.zones
            self._hass.bus.async_fire(NEST_EVENT, message)


class NestStreamUpdateCallback:
    """Handle stream manager updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: NestConfigEntry,
        supported_traits: Callable[[], set[TraitType]],
    ) -> None:
        """Initialize NestStreamUpdateCallback."""
        self._hass = hass
        self._config_entry = config_entry
        self._supported_traits = supported_traits

    def _supported_traits(self, device_id: str) -> list[str]:
        if (
            not self._config_entry.runtime_data
            or not (device_manager := self._config_entry.runtime_data.device_manager)
            or not (device := device_manager.devices.get(device_id))
        ):
            return []
        return list(device.traits)


async def async_setup_entry(hass: HomeAssistant, entry: NestConfigEntry) -> bool:
    """Set up Nest from a config entry with dispatch between old/new flows."""

    # Apply IPv4 preference fix for IPv6 network connectivity issues
    # This resolves "Timeout in streaming_pull" errors on systems with
    # partial IPv6 configuration by automatically preferring IPv4 connections
    try:
        _configure_ipv4_preference()
    except Exception as e:
        _LOGGER.warning(
            "Failed to configure IPv4 preference for Google Cloud connections: %s", e
        )

    if DATA_SDM not in entry.data:
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        return False

    if entry.unique_id != entry.data[CONF_PROJECT_ID]:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_PROJECT_ID]
        )

    auth = await api.new_auth(hass, entry)
    try:
        await auth.async_get_access_token()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err

    subscriber = await api.new_subscriber(hass, entry, auth)
    if not subscriber:
        return False
    # Keep media for last N events in memory
    subscriber.cache_policy.event_cache_size = EVENT_MEDIA_CACHE_SIZE
    subscriber.cache_policy.fetch = True
    # Use disk backed event media store
    subscriber.cache_policy.store = await async_get_media_event_store(hass, subscriber)
    subscriber.cache_policy.transcoder = await async_get_transcoder(hass)

    async def async_config_reload() -> None:
        await hass.config_entries.async_reload(entry.entry_id)

    update_callback = SignalUpdateCallback(hass, async_config_reload, entry)
    subscriber.set_update_callback(update_callback.async_handle_event)

    try:
        _LOGGER.debug("Starting Nest subscriber with network configuration applied")
        unsub = await subscriber.start_async()
    except AuthException as err:
        raise ConfigEntryAuthFailed(
            f"Subscriber authentication error: {err!s}"
        ) from err
    except ConfigurationException as err:
        _LOGGER.error("Configuration error: %s", err)
        return False
    except SubscriberException as err:
        # Enhanced error handling for IPv6-related timeouts
        error_msg = str(err).lower()
        if "timeout" in error_msg and "streaming_pull" in error_msg:
            ipv4_enabled = os.environ.get("GRPC_PREFER_IPV4") == "1"
            if ipv4_enabled:
                _LOGGER.error(
                    "Nest subscriber timeout persists despite IPv4 preference. "
                    "Try disabling IPv6 completely: "
                    "'ha network update <interface> --ipv6-method disabled'. "
                    "See: https://github.com/home-assistant/core/issues/139485"
                )
            else:
                _LOGGER.error(
                    "Nest subscriber timeout detected (likely IPv6 network issue). "
                    "IPv4 preference may not have been applied correctly. "
                    "Manual workaround: disable IPv6 via "
                    "'ha network update <interface> --ipv6-method disabled'"
                )
        raise ConfigEntryNotReady(f"Subscriber error: {err!s}") from err

    try:
        device_manager = await subscriber.async_get_device_manager()
    except ApiException as err:
        unsub()
        raise ConfigEntryNotReady(f"Device manager error: {err!s}") from err

    @callback
    def on_hass_stop(_: Event) -> None:
        """Close connection when hass stops."""
        unsub()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )
    entry.runtime_data = NestData(subscriber, device_manager)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("Nest integration setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NestConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class NestEventViewBase(HomeAssistantView, ABC):
    """Base class for event media views."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize NestEventViewBase."""
        self._hass = hass

    @property
    def nest_data(self) -> NestData | None:
        """Return the NestData for this view."""
        for config_entry in self._hass.config_entries.async_entries(DOMAIN):
            if config_entry.runtime_data:
                return config_entry.runtime_data
        return None

    @abstractmethod
    async def load_media(self, nest_device: Device, event_token: str) -> Media | None:
        """Load the specified media."""

    @abstractmethod
    async def handle_media(self, media: Media) -> web.StreamResponse:
        """Process the specified media."""

    async def get(
        self, request: web.Request, device_id: str, event_token: str
    ) -> web.StreamResponse:
        """Handle request to get media."""
        user = request.get(KEY_HASS_USER)
        if user is None:
            raise Unauthorized()
        if not user.permissions.check_entity(device_id, POLICY_READ):
            raise Unauthorized()

        nest_data = self.nest_data
        if nest_data is None:
            _LOGGER.debug("Unable to find nest_data")
            return web.Response(status=HTTPStatus.SERVICE_UNAVAILABLE)

        device_manager = nest_data.device_manager
        nest_device = device_manager.devices.get(device_id)
        if nest_device is None:
            _LOGGER.debug("Unable to find device for device_id %s", device_id)
            return web.Response(status=HTTPStatus.NOT_FOUND)

        try:
            media = await self.load_media(nest_device, event_token)
        except ApiException as err:
            _LOGGER.debug("Unable to load media %s: %s", event_token, err)
            return web.Response(status=HTTPStatus.NOT_FOUND)

        if media is None:
            _LOGGER.debug("No media found for event token %s", event_token)
            return web.Response(status=HTTPStatus.NOT_FOUND)

        return await self.handle_media(media)


class NestEventMediaView(NestEventViewBase):
    """Returns media for related to events for a specific device.

    This is primarily used to render media for events for MediaSource. The media type
    depends on the specific device e.g. an image, or a movie clip preview.
    """

    url = "/api/nest/event_media/{device_id}/{event_token}"
    name = "api:nest:event_media"

    async def load_media(self, nest_device: Device, event_token: str) -> Media | None:
        """Load the specified media."""
        return await nest_device.event_media_manager.get_media_from_token(event_token)

    async def handle_media(self, media: Media) -> web.StreamResponse:
        """Process the specified media."""
        return web.Response(body=media.contents, content_type=media.content_type)


class NestEventMediaThumbnailView(NestEventViewBase):
    """Returns media for related to events for a specific device.

    This is primarily used to render media for events for MediaSource. The media type
    depends on the specific device e.g. an image, or a movie clip preview.

    mp4 clips are transcoded and thumbnailed by the SDM transcoder. jpgs are thumbnailed
    from the original in this view.
    """

    url = "/api/nest/event_media/{device_id}/{event_token}/thumbnail"
    name = "api:nest:event_media"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize NestEventMediaThumbnailView."""
        super().__init__(hass)
        self._lock = asyncio.Lock()
        self.hass = hass

    async def load_media(self, nest_device: Device, event_token: str) -> Media | None:
        """Load the specified media."""
        if CameraClipPreviewTrait.NAME in nest_device.traits:
            async with self._lock:  # Only one transcode subprocess at a time
                return (
                    await nest_device.event_media_manager.get_clip_thumbnail_from_token(
                        event_token
                    )
                )
        return await nest_device.event_media_manager.get_media_from_token(event_token)

    async def handle_media(self, media: Media) -> web.StreamResponse:
        """Start a GET request."""
        contents = media.contents
        if (content_type := media.content_type) == "image/jpeg":
            image = Image(media.event_image_type.content_type, contents)
            contents = img_util.scale_jpeg_camera_image(
                image, THUMBNAIL_SIZE_PX, THUMBNAIL_SIZE_PX
            )
        return web.Response(body=contents, content_type=content_type)
