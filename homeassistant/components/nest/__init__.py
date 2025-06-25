"""Support for Nest devices."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Awaitable, Callable
from http import HTTPStatus
import logging

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
        supported_traits = self._supported_traits(device_id)
        for api_event_type, image_event in events.items():
            if not (event_type := EVENT_NAME_MAP.get(api_event_type)):
                continue
            nest_event_id = image_event.event_token
            message = {
                "device_id": device_entry.id,
                "type": event_type,
                "timestamp": event_message.timestamp,
                "nest_event_id": nest_event_id,
            }
            if (
                TraitType.CAMERA_EVENT_IMAGE in supported_traits
                or TraitType.CAMERA_CLIP_PREVIEW in supported_traits
            ):
                attachment = {
                    "image": EVENT_THUMBNAIL_URL_FORMAT.format(
                        device_id=device_entry.id, event_token=image_event.event_token
                    )
                }
                if TraitType.CAMERA_CLIP_PREVIEW in supported_traits:
                    attachment["video"] = EVENT_MEDIA_API_URL_FORMAT.format(
                        device_id=device_entry.id, event_token=image_event.event_token
                    )
                message["attachment"] = attachment
            if image_event.zones:
                message["zones"] = image_event.zones
            self._hass.bus.async_fire(NEST_EVENT, message)

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
        unsub = await subscriber.start_async()
    except AuthException as err:
        raise ConfigEntryAuthFailed(
            f"Subscriber authentication error: {err!s}"
        ) from err
    except ConfigurationException as err:
        _LOGGER.error("Configuration error: %s", err)
        return False
    except SubscriberException as err:
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

    entry.async_on_unload(unsub)
    entry.runtime_data = NestData(
        subscriber=subscriber,
        device_manager=device_manager,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NestConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: NestConfigEntry) -> None:
    """Handle removal of pubsub subscriptions created during config flow."""
    if (
        DATA_SDM not in entry.data
        or not (
            CONF_SUBSCRIPTION_NAME in entry.data or CONF_SUBSCRIBER_ID in entry.data
        )
        or CONF_SUBSCRIBER_ID_IMPORTED in entry.data
    ):
        return
    if (subscription_name := entry.data.get(CONF_SUBSCRIPTION_NAME)) is None:
        subscription_name = entry.data[CONF_SUBSCRIBER_ID]
    admin_client = api.new_pubsub_admin_client(
        hass,
        access_token=entry.data["token"]["access_token"],
        cloud_project_id=entry.data[CONF_CLOUD_PROJECT_ID],
    )
    _LOGGER.debug("Deleting subscription '%s'", subscription_name)
    try:
        await admin_client.delete_subscription(subscription_name)
    except ApiException as err:
        _LOGGER.warning(
            (
                "Unable to delete subscription '%s'; Will be automatically cleaned up"
                " by cloud console: %s"
            ),
            subscription_name,
            err,
        )


class NestEventViewBase(HomeAssistantView, ABC):
    """Base class for media event APIs."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize NestEventViewBase."""
        self.hass = hass

    async def get(
        self, request: web.Request, device_id: str, event_token: str
    ) -> web.StreamResponse:
        """Start a GET request."""
        user = request[KEY_HASS_USER]
        entity_registry = er.async_get(self.hass)
        for entry in async_entries_for_device(entity_registry, device_id):
            if not user.permissions.check_entity(entry.entity_id, POLICY_READ):
                raise Unauthorized(entity_id=entry.entity_id)

        devices = async_get_media_source_devices(self.hass)
        if not (nest_device := devices.get(device_id)):
            return self._json_error(
                f"No Nest Device found for '{device_id}'", HTTPStatus.NOT_FOUND
            )
        try:
            media = await self.load_media(nest_device, event_token)
        except DecodeException:
            return self._json_error(
                f"Event token was invalid '{event_token}'", HTTPStatus.NOT_FOUND
            )
        except ApiException as err:
            raise HomeAssistantError("Unable to fetch media for event") from err
        if not media:
            return self._json_error(
                f"No event found for event_id '{event_token}'", HTTPStatus.NOT_FOUND
            )
        return await self.handle_media(media)

    @abstractmethod
    async def load_media(self, nest_device: Device, event_token: str) -> Media | None:
        """Load the specified media."""

    @abstractmethod
    async def handle_media(self, media: Media) -> web.StreamResponse:
        """Process the specified media."""

    def _json_error(self, message: str, status: HTTPStatus) -> web.StreamResponse:
        """Return a json error message with additional logging."""
        _LOGGER.debug(message)
        return self.json_message(message, status)


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
