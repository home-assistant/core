"""Support for Nest devices."""
from __future__ import annotations

from http import HTTPStatus
import logging

from aiohttp import web
from google_nest_sdm.event import EventMessage
from google_nest_sdm.exceptions import (
    AuthException,
    ConfigurationException,
    GoogleNestException,
)
import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components.http.const import KEY_HASS_USER
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_MONITORED_CONDITIONS,
    CONF_SENSORS,
    CONF_STRUCTURE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    Unauthorized,
)
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers.typing import ConfigType

from . import api, config_flow
from .const import (
    CONF_PROJECT_ID,
    CONF_SUBSCRIBER_ID,
    DATA_NEST_CONFIG,
    DATA_SDM,
    DATA_SUBSCRIBER,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    OOB_REDIRECT_URI,
)
from .events import EVENT_NAME_MAP, NEST_EVENT
from .legacy import async_setup_legacy, async_setup_legacy_entry
from .media_source import get_media_source_devices

_LOGGER = logging.getLogger(__name__)

DATA_NEST_UNAVAILABLE = "nest_unavailable"

NEST_SETUP_NOTIFICATION = "nest_setup"

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
PLATFORMS = ["sensor", "camera", "climate"]
WEB_AUTH_DOMAIN = DOMAIN
INSTALLED_AUTH_DOMAIN = f"{DOMAIN}.installed"

# Fetch media for events with an in memory cache. The largest media items
# are mp4 clips at ~90kb each, so this totals a few MB per camera.
# Note: Media for events can only be published within 30 seconds of the event
EVENT_MEDIA_CACHE_SIZE = 64


class WebAuth(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """OAuth implementation using OAuth for web applications."""

    name = "OAuth for Web"

    def __init__(
        self, hass: HomeAssistant, client_id: str, client_secret: str, project_id: str
    ) -> None:
        """Initialize WebAuth."""
        super().__init__(
            hass,
            WEB_AUTH_DOMAIN,
            client_id,
            client_secret,
            OAUTH2_AUTHORIZE.format(project_id=project_id),
            OAUTH2_TOKEN,
        )


class InstalledAppAuth(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """OAuth implementation using OAuth for installed applications."""

    name = "OAuth for Apps"

    def __init__(
        self, hass: HomeAssistant, client_id: str, client_secret: str, project_id: str
    ) -> None:
        """Initialize InstalledAppAuth."""
        super().__init__(
            hass,
            INSTALLED_AUTH_DOMAIN,
            client_id,
            client_secret,
            OAUTH2_AUTHORIZE.format(project_id=project_id),
            OAUTH2_TOKEN,
        )

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        return OOB_REDIRECT_URI


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Nest components with dispatch between old/new flows."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    if CONF_PROJECT_ID not in config[DOMAIN]:
        return await async_setup_legacy(hass, config)

    # For setup of ConfigEntry below
    hass.data[DOMAIN][DATA_NEST_CONFIG] = config[DOMAIN]
    project_id = config[DOMAIN][CONF_PROJECT_ID]
    config_flow.NestFlowHandler.register_sdm_api(hass)
    config_flow.NestFlowHandler.async_register_implementation(
        hass,
        InstalledAppAuth(
            hass,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            project_id,
        ),
    )
    config_flow.NestFlowHandler.async_register_implementation(
        hass,
        WebAuth(
            hass,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            project_id,
        ),
    )

    return True


class SignalUpdateCallback:
    """An EventCallback invoked when new events arrive from subscriber."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize EventCallback."""
        self._hass = hass

    async def async_handle_event(self, event_message: EventMessage) -> None:
        """Process an incoming EventMessage."""
        if not event_message.resource_update_name:
            return
        device_id = event_message.resource_update_name
        if not (events := event_message.resource_update_events):
            return
        _LOGGER.debug("Event Update %s", events.keys())
        device_registry = await self._hass.helpers.device_registry.async_get_registry()
        device_entry = device_registry.async_get_device({(DOMAIN, device_id)})
        if not device_entry:
            return
        for api_event_type, image_event in events.items():
            if not (event_type := EVENT_NAME_MAP.get(api_event_type)):
                continue
            message = {
                "device_id": device_entry.id,
                "type": event_type,
                "timestamp": event_message.timestamp,
                "nest_event_id": image_event.event_session_id,
            }
            self._hass.bus.async_fire(NEST_EVENT, message)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nest from a config entry with dispatch between old/new flows."""

    if DATA_SDM not in entry.data:
        return await async_setup_legacy_entry(hass, entry)

    subscriber = await api.new_subscriber(hass, entry)
    if not subscriber:
        return False
    # Keep media for last N events in memory
    subscriber.cache_policy.event_cache_size = EVENT_MEDIA_CACHE_SIZE
    subscriber.cache_policy.fetch = True

    callback = SignalUpdateCallback(hass)
    subscriber.set_update_callback(callback.async_handle_event)
    try:
        await subscriber.start_async()
    except AuthException as err:
        _LOGGER.debug("Subscriber authentication error: %s", err)
        raise ConfigEntryAuthFailed from err
    except ConfigurationException as err:
        _LOGGER.error("Configuration error: %s", err)
        subscriber.stop_async()
        return False
    except GoogleNestException as err:
        if DATA_NEST_UNAVAILABLE not in hass.data[DOMAIN]:
            _LOGGER.error("Subscriber error: %s", err)
            hass.data[DOMAIN][DATA_NEST_UNAVAILABLE] = True
        subscriber.stop_async()
        raise ConfigEntryNotReady from err

    try:
        await subscriber.async_get_device_manager()
    except GoogleNestException as err:
        if DATA_NEST_UNAVAILABLE not in hass.data[DOMAIN]:
            _LOGGER.error("Device manager error: %s", err)
            hass.data[DOMAIN][DATA_NEST_UNAVAILABLE] = True
        subscriber.stop_async()
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN].pop(DATA_NEST_UNAVAILABLE, None)
    hass.data[DOMAIN][DATA_SUBSCRIBER] = subscriber

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    hass.http.register_view(NestEventMediaView(hass))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if DATA_SDM not in entry.data:
        # Legacy API
        return True
    _LOGGER.debug("Stopping nest subscriber")
    subscriber = hass.data[DOMAIN][DATA_SUBSCRIBER]
    subscriber.stop_async()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(DATA_SUBSCRIBER)
        hass.data[DOMAIN].pop(DATA_NEST_UNAVAILABLE, None)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of pubsub subscriptions created during config flow."""
    if DATA_SDM not in entry.data or CONF_SUBSCRIBER_ID not in entry.data:
        return

    subscriber = await api.new_subscriber(hass, entry)
    if not subscriber:
        return
    _LOGGER.debug("Deleting subscriber '%s'", subscriber.subscriber_id)
    try:
        await subscriber.delete_subscription()
    except GoogleNestException as err:
        _LOGGER.warning(
            "Unable to delete subscription '%s'; Will be automatically cleaned up by cloud console: %s",
            subscriber.subscriber_id,
            err,
        )
    finally:
        subscriber.stop_async()


class NestEventMediaView(HomeAssistantView):
    """Returns media for related to events for a specific device.

    This is primarily used to render media for events for MediaSource. The media type
    depends on the specific device e.g. an image, or a movie clip preview.
    """

    url = "/api/nest/event_media/{device_id}/{event_id}"
    name = "api:nest:event_media"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize NestEventMediaView."""
        self.hass = hass

    async def get(
        self, request: web.Request, device_id: str, event_id: str
    ) -> web.StreamResponse:
        """Start a GET request."""
        user = request[KEY_HASS_USER]
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        for entry in async_entries_for_device(entity_registry, device_id):
            if not user.permissions.check_entity(entry.entity_id, POLICY_READ):
                raise Unauthorized(entity_id=entry.entity_id)

        devices = await get_media_source_devices(self.hass)
        if not (nest_device := devices.get(device_id)):
            return self._json_error(
                f"No Nest Device found for '{device_id}'", HTTPStatus.NOT_FOUND
            )
        try:
            event_media = await nest_device.event_media_manager.get_media(event_id)
        except GoogleNestException as err:
            raise HomeAssistantError("Unable to fetch media for event") from err
        if not event_media:
            return self._json_error(
                f"No event found for event_id '{event_id}'", HTTPStatus.NOT_FOUND
            )
        media = event_media.media
        return web.Response(
            body=media.contents, content_type=media.event_image_type.content_type
        )

    def _json_error(self, message: str, status: HTTPStatus) -> web.StreamResponse:
        """Return a json error message with additional logging."""
        _LOGGER.debug(message)
        return self.json_message(message, status)
