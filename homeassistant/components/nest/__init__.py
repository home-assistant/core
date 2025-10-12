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
    DecodeException,
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
    HomeAssistantError,
    Unauthorized,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers.typing import ConfigType

from . import api
from .const import (
    CONF_CLOUD_PROJECT_ID,
    CONF_PROJECT_ID,
    CONF_SUBSCRIBER_ID,
    CONF_SUBSCRIBER_ID_IMPORTED,
    CONF_SUBSCRIPTION_NAME,
    DATA_SDM,
    DOMAIN,
)
from .events import EVENT_NAME_MAP, NEST_EVENT
from .media_source import (
    EVENT_MEDIA_API_URL_FORMAT,
    EVENT_THUMBNAIL_URL_FORMAT,
    async_get_media_event_store,
    async_get_media_source_devices,
    async_get_transcoder,
)
from .types import NestConfigEntry, NestData

_LOGGER = logging.getLogger(__name__)


def _test_ipv6_connectivity() -> bool:
    """
    Test IPv6 connectivity to Google services.
    
    Returns True if IPv6 connectivity is working, False if IPv4 preference should be used.
    This helps detect partial IPv6 configurations that cause subscriber timeouts.
    
    Based on GitHub issues #139485 and #147815.
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
    
    Based on GitHub issues #139485 and #147815.
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
    {vol.Optional(CONF_MONITORED_CONDITIONS): vol.All(cv.ensure_list)}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                # Required to use the new API (optional for compatibility)
                vol.Optional(CONF_PROJECT_ID): cv.string,
                vol.Optional(CONF_SUBSCRIBER_ID): cv.string,
                # Config that only currently works on the old API
                vol.Optional(CONF_STRUCTURE): vol.All(cv.ensure_list, [cv.string]),
                vol.Optional(CONF_SENSORS): SENSOR_SCHEMA,
                vol.Optional(CONF_BINARY_SENSORS): SENSOR_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Cache events for 5 minutes
EVENT_MEDIA_CACHE_SIZE = 100


class NestDeviceDataManager:
    """Manages device id to api data mapping."""

    def __init__(self, auth: api.AsyncConfigEntryAuth, subscriber: api.GoogleNestSubscriber) -> None:
        """Initialize NestDeviceDataManager."""
        self._auth = auth
        self._subscriber = subscriber

    @property
    def auth(self) -> api.AsyncConfigEntryAuth:
        """Return the auth object."""
        return self._auth

    @property
    def subscriber(self) -> api.GoogleNestSubscriber:
        """Return the subscriber object."""
        return self._subscriber


class SignalUpdateCallback:
    """An EventCallback invoked when subscriber receives an event."""

    def __init__(self, device_manager: NestDeviceDataManager) -> None:
        """Initialize EventCallback."""
        self._device_manager = device_manager

    async def async_handle_event(self, event_message: EventMessage) -> None:
        """Process an incoming EventMessage."""
        device_id = event_message.resource_update_name
        if device_id is not None:
            # Update device in place
            if device := self._device_manager.subscriber.cache_policy.devices.get(device_id):
                await device.async_update_traits(event_message.resource_update_traits)
                device.dispatch_event(event_message)


class NestEventMediaManager:
    """Nest Event Media."""

    def __init__(
        self,
        subscriber: api.GoogleNestSubscriber,
        media_manager_cls: type[api.MediaEventStore],
    ) -> None:
        """Initialize NestEventMediaManager."""
        self._subscriber = subscriber
        self._media_manager_cls = media_manager_cls

    async def async_handle_media_event(
        self,
        event_message: EventMessage,
    ) -> None:
        """Handle media event."""
        # Media event is fired to request a still image
        pass


class SupportedTraits:
    """Base class for providing supported traits."""

    def __init__(self, supported_traits: list[str]) -> None:
        """Initialize Supported Traits."""
        self._supported_traits_list = supported_traits

    def _get_supported_traits_for_device(self, device_id: str) -> list[str]:
        """Return a list of supported traits for a device."""
        # Use traits from the subscriber's device cache if available
        if hasattr(self, '_subscriber') and self._subscriber.cache_policy.devices:
            if device := self._subscriber.cache_policy.devices.get(device_id):
                return list(device.traits)
        return self._supported_traits_list


async def async_setup_entry(hass: HomeAssistant, entry: NestConfigEntry) -> bool:
    """Set up Nest from a config entry with dispatch between old/new flows."""
    _configure_ipv4_preference()
    
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

    try:
        unsub = await subscriber.start_async()
    except AuthException as err:
        _LOGGER.debug("Nest authentication error: %s", err)
        raise ConfigEntryAuthFailed from err
    except ConfigurationException as err:
        _LOGGER.error("Configuration error: %s", err)
        subscriber.stop_async()
        raise ConfigEntryNotReady from err
    except SubscriberException as err:
        if "Timeout in streaming_pull" in str(err):
            _LOGGER.error(
                "Nest subscriber timeout - this may be caused by IPv6 network issues. "
                "IPv4 preference has been automatically configured. If the issue persists, "
                "see: https://github.com/home-assistant/core/issues/139485"
            )
        raise ConfigEntryNotReady from err
    except Exception as err:  # noqa: BLE001
        _LOGGER.error("Nest subscriber error: %s", err)
        subscriber.stop_async()
        raise ConfigEntryNotReady from err

    device_manager = NestDeviceDataManager(auth, subscriber)
    callback = SignalUpdateCallback(device_manager)
    subscriber.set_update_callback(callback.async_handle_event)

    entry.async_on_unload(unsub)
    entry.runtime_data = NestData(subscriber, device_manager)

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.CAMERA, Platform.CLIMATE, Platform.SENSOR])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NestConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, [Platform.CAMERA, Platform.CLIMATE, Platform.SENSOR]
    )


class NestThumbnailView(HomeAssistantView):
    """Nest view to handle thumbnail requests."""

    url = EVENT_THUMBNAIL_URL_FORMAT
    name = "api:nest:thumbnail"
    requires_auth = True

    def __init__(self, store: api.MediaEventStore) -> None:
        """Initialize the view."""
        self._store = store

    async def get(self, request: web.Request, device_id: str, event_id: str) -> web.StreamResponse:
        """Start stream."""
        user = request.get(KEY_HASS_USER)
        if user is None:
            raise Unauthorized()
        
        # Check permissions for entities associated with this device
        hass = request.app["hass"]
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        
        if device_entry := device_registry.async_get_device({(DOMAIN, device_id)}):
            entities = async_entries_for_device(entity_registry, device_entry.id)
            if entities and not user.permissions.check_entity(entities[0].entity_id, POLICY_READ):
                raise Unauthorized()
        else:
            raise Unauthorized()

        try:
            image_bytes = await self._store.async_get_media(event_id, "thumbnail.jpg")
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error retrieving media for event %s: %s", event_id, err)
            raise web.HTTPNotFound() from err

        if image_bytes is None:
            raise web.HTTPNotFound()

        return web.Response(
            body=image_bytes,
            content_type="image/jpeg",
        )


class NestEventMediaView(HomeAssistantView):
    """Nest view to handle event media requests."""

    url = EVENT_MEDIA_API_URL_FORMAT
    name = "api:nest:event_media"
    requires_auth = True

    def __init__(self, store: api.MediaEventStore) -> None:
        """Initialize the view."""
        self._store = store

    async def get(self, request: web.Request, device_id: str, event_id: str, media_id: str) -> web.StreamResponse:
        """Start stream."""
        user = request.get(KEY_HASS_USER)
        if user is None:
            raise Unauthorized()
        
        # Check permissions for entities associated with this device
        hass = request.app["hass"]
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        
        if device_entry := device_registry.async_get_device({(DOMAIN, device_id)}):
            entities = async_entries_for_device(entity_registry, device_entry.id)
            if entities and not user.permissions.check_entity(entities[0].entity_id, POLICY_READ):
                raise Unauthorized()
        else:
            raise Unauthorized()

        try:
            media_contents = await self._store.async_get_media(event_id, media_id)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error retrieving media for event %s: %s", event_id, err)
            raise web.HTTPNotFound() from err

        if media_contents is None:
            raise web.HTTPNotFound()

        content_type, _ = img_util.get_image_type(media_contents)
        return web.Response(
            body=media_contents,
            content_type=content_type,
        )
