"""Component to integrate the Home Assistant cloud."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from enum import Enum

from hass_nabucasa import Cloud
import voluptuous as vol

from homeassistant.components import alexa, google_assistant
from homeassistant.const import (
    CONF_DESCRIPTION,
    CONF_MODE,
    CONF_NAME,
    CONF_REGION,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entityfilter
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util.aiohttp import MockRequest

from . import account_link, http_api
from .client import CloudClient
from .const import (
    CONF_ACCOUNT_LINK_URL,
    CONF_ACME_DIRECTORY_SERVER,
    CONF_ALEXA,
    CONF_ALEXA_ACCESS_TOKEN_URL,
    CONF_ALIASES,
    CONF_CLOUDHOOK_CREATE_URL,
    CONF_COGNITO_CLIENT_ID,
    CONF_ENTITY_CONFIG,
    CONF_FILTER,
    CONF_GOOGLE_ACTIONS,
    CONF_GOOGLE_ACTIONS_REPORT_STATE_URL,
    CONF_RELAYER,
    CONF_REMOTE_API_URL,
    CONF_SUBSCRIPTION_INFO_URL,
    CONF_USER_POOL_ID,
    CONF_VOICE_API_URL,
    DOMAIN,
    MODE_DEV,
    MODE_PROD,
)
from .prefs import CloudPreferences
from .repairs import async_manage_legacy_subscription_issue
from .subscription import async_subscription_info

DEFAULT_MODE = MODE_PROD

SERVICE_REMOTE_CONNECT = "remote_connect"
SERVICE_REMOTE_DISCONNECT = "remote_disconnect"

SIGNAL_CLOUD_CONNECTION_STATE = "CLOUD_CONNECTION_STATE"


ALEXA_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DESCRIPTION): cv.string,
        vol.Optional(alexa.CONF_DISPLAY_CATEGORIES): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)

GOOGLE_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_ALIASES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(google_assistant.CONF_ROOM_HINT): cv.string,
    }
)

ASSISTANT_SCHEMA = vol.Schema(
    {vol.Optional(CONF_FILTER, default=dict): entityfilter.FILTER_SCHEMA}
)

ALEXA_SCHEMA = ASSISTANT_SCHEMA.extend(
    {vol.Optional(CONF_ENTITY_CONFIG): {cv.entity_id: ALEXA_ENTITY_SCHEMA}}
)

GACTIONS_SCHEMA = ASSISTANT_SCHEMA.extend(
    {vol.Optional(CONF_ENTITY_CONFIG): {cv.entity_id: GOOGLE_ENTITY_SCHEMA}}
)

# pylint: disable=no-value-for-parameter
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.In(
                    [MODE_DEV, MODE_PROD]
                ),
                vol.Optional(CONF_COGNITO_CLIENT_ID): str,
                vol.Optional(CONF_USER_POOL_ID): str,
                vol.Optional(CONF_REGION): str,
                vol.Optional(CONF_RELAYER): str,
                vol.Optional(CONF_SUBSCRIPTION_INFO_URL): vol.Url(),
                vol.Optional(CONF_CLOUDHOOK_CREATE_URL): vol.Url(),
                vol.Optional(CONF_REMOTE_API_URL): vol.Url(),
                vol.Optional(CONF_ACME_DIRECTORY_SERVER): vol.Url(),
                vol.Optional(CONF_ALEXA): ALEXA_SCHEMA,
                vol.Optional(CONF_GOOGLE_ACTIONS): GACTIONS_SCHEMA,
                vol.Optional(CONF_ALEXA_ACCESS_TOKEN_URL): vol.Url(),
                vol.Optional(CONF_GOOGLE_ACTIONS_REPORT_STATE_URL): vol.Url(),
                vol.Optional(CONF_ACCOUNT_LINK_URL): vol.Url(),
                vol.Optional(CONF_VOICE_API_URL): vol.Url(),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class CloudNotAvailable(HomeAssistantError):
    """Raised when an action requires the cloud but it's not available."""


class CloudNotConnected(CloudNotAvailable):
    """Raised when an action requires the cloud but it's not connected."""


class CloudConnectionState(Enum):
    """Cloud connection state."""

    CLOUD_CONNECTED = "cloud_connected"
    CLOUD_DISCONNECTED = "cloud_disconnected"


@bind_hass
@callback
def async_is_logged_in(hass: HomeAssistant) -> bool:
    """Test if user is logged in.

    Note: This returns True even if not currently connected to the cloud.
    """
    return DOMAIN in hass.data and hass.data[DOMAIN].is_logged_in


@bind_hass
@callback
def async_is_connected(hass: HomeAssistant) -> bool:
    """Test if connected to the cloud."""
    return DOMAIN in hass.data and hass.data[DOMAIN].iot.connected


@callback
def async_listen_connection_change(
    hass: HomeAssistant,
    target: Callable[[CloudConnectionState], Awaitable[None] | None],
) -> Callable[[], None]:
    """Notify on connection state changes."""
    return async_dispatcher_connect(hass, SIGNAL_CLOUD_CONNECTION_STATE, target)


@bind_hass
@callback
def async_active_subscription(hass: HomeAssistant) -> bool:
    """Test if user has an active subscription."""
    return async_is_logged_in(hass) and not hass.data[DOMAIN].subscription_expired


@bind_hass
async def async_create_cloudhook(hass: HomeAssistant, webhook_id: str) -> str:
    """Create a cloudhook."""
    if not async_is_connected(hass):
        raise CloudNotConnected

    if not async_is_logged_in(hass):
        raise CloudNotAvailable

    hook = await hass.data[DOMAIN].cloudhooks.async_create(webhook_id, True)
    return hook["cloudhook_url"]


@bind_hass
async def async_delete_cloudhook(hass: HomeAssistant, webhook_id: str) -> None:
    """Delete a cloudhook."""
    if DOMAIN not in hass.data:
        raise CloudNotAvailable

    await hass.data[DOMAIN].cloudhooks.async_delete(webhook_id)


@bind_hass
@callback
def async_remote_ui_url(hass: HomeAssistant) -> str:
    """Get the remote UI URL."""
    if not async_is_logged_in(hass):
        raise CloudNotAvailable

    if not hass.data[DOMAIN].client.prefs.remote_enabled:
        raise CloudNotAvailable

    if not (remote_domain := hass.data[DOMAIN].client.prefs.remote_domain):
        raise CloudNotAvailable

    return f"https://{remote_domain}"


def is_cloudhook_request(request):
    """Test if a request came from a cloudhook.

    Async friendly.
    """
    return isinstance(request, MockRequest)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the Home Assistant cloud."""
    # Process configs
    if DOMAIN in config:
        kwargs = dict(config[DOMAIN])
    else:
        kwargs = {CONF_MODE: DEFAULT_MODE}

    # Alexa/Google custom config
    alexa_conf = kwargs.pop(CONF_ALEXA, None) or ALEXA_SCHEMA({})
    google_conf = kwargs.pop(CONF_GOOGLE_ACTIONS, None) or GACTIONS_SCHEMA({})

    # Cloud settings
    prefs = CloudPreferences(hass)
    await prefs.async_initialize()

    # Initialize Cloud
    websession = async_get_clientsession(hass)
    client = CloudClient(hass, prefs, websession, alexa_conf, google_conf)
    cloud = hass.data[DOMAIN] = Cloud(client, **kwargs)

    async def _shutdown(event):
        """Shutdown event."""
        await cloud.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)

    _remote_handle_prefs_updated(cloud)

    async def _service_handler(service: ServiceCall) -> None:
        """Handle service for cloud."""
        if service.service == SERVICE_REMOTE_CONNECT:
            await prefs.async_update(remote_enabled=True)
        elif service.service == SERVICE_REMOTE_DISCONNECT:
            await prefs.async_update(remote_enabled=False)

    async_register_admin_service(hass, DOMAIN, SERVICE_REMOTE_CONNECT, _service_handler)
    async_register_admin_service(
        hass, DOMAIN, SERVICE_REMOTE_DISCONNECT, _service_handler
    )

    loaded = False

    async def async_startup_repairs(_=None) -> None:
        """Create repair issues after startup."""
        if not cloud.is_logged_in:
            return

        if subscription_info := await async_subscription_info(cloud):
            async_manage_legacy_subscription_issue(hass, subscription_info)

    async def _on_connect():
        """Discover RemoteUI binary sensor."""
        nonlocal loaded

        # Prevent multiple discovery
        if loaded:
            return
        loaded = True

        await async_load_platform(hass, Platform.BINARY_SENSOR, DOMAIN, {}, config)
        await async_load_platform(hass, Platform.STT, DOMAIN, {}, config)
        await async_load_platform(hass, Platform.TTS, DOMAIN, {}, config)

        async_dispatcher_send(
            hass, SIGNAL_CLOUD_CONNECTION_STATE, CloudConnectionState.CLOUD_CONNECTED
        )

    async def _on_disconnect():
        """Handle cloud disconnect."""
        async_dispatcher_send(
            hass, SIGNAL_CLOUD_CONNECTION_STATE, CloudConnectionState.CLOUD_DISCONNECTED
        )

    async def _on_initialized():
        """Update preferences."""
        await prefs.async_update(remote_domain=cloud.remote.instance_domain)

    cloud.iot.register_on_connect(_on_connect)
    cloud.iot.register_on_disconnect(_on_disconnect)
    cloud.register_on_initialized(_on_initialized)

    await cloud.initialize()
    await http_api.async_setup(hass)

    account_link.async_setup(hass)

    async_call_later(
        hass=hass,
        delay=timedelta(hours=1),
        action=async_startup_repairs,
    )

    return True


@callback
def _remote_handle_prefs_updated(cloud: Cloud) -> None:
    """Handle remote preferences updated."""
    cur_pref = cloud.client.prefs.remote_enabled
    lock = asyncio.Lock()

    # Sync remote connection with prefs
    async def remote_prefs_updated(prefs: CloudPreferences) -> None:
        """Update remote status."""
        nonlocal cur_pref

        async with lock:
            if prefs.remote_enabled == cur_pref:
                return

            if cur_pref := prefs.remote_enabled:
                await cloud.remote.connect()
            else:
                await cloud.remote.disconnect()

    cloud.client.prefs.async_listen_updates(remote_prefs_updated)
