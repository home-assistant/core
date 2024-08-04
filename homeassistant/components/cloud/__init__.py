"""Component to integrate the Home Assistant cloud."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from enum import Enum
from typing import cast

from hass_nabucasa import Cloud
import voluptuous as vol

from homeassistant.components import alexa, google_assistant
from homeassistant.config_entries import SOURCE_SYSTEM, ConfigEntry
from homeassistant.const import (
    CONF_DESCRIPTION,
    CONF_MODE,
    CONF_NAME,
    CONF_REGION,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HassJob, HomeAssistant, ServiceCall, callback
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
from homeassistant.util.signal_type import SignalType

from . import account_link, http_api
from .client import CloudClient
from .const import (
    CONF_ACCOUNT_LINK_SERVER,
    CONF_ACCOUNTS_SERVER,
    CONF_ACME_SERVER,
    CONF_ALEXA,
    CONF_ALEXA_SERVER,
    CONF_ALIASES,
    CONF_CLOUDHOOK_SERVER,
    CONF_COGNITO_CLIENT_ID,
    CONF_ENTITY_CONFIG,
    CONF_FILTER,
    CONF_GOOGLE_ACTIONS,
    CONF_RELAYER_SERVER,
    CONF_REMOTESTATE_SERVER,
    CONF_SERVICEHANDLERS_SERVER,
    CONF_THINGTALK_SERVER,
    CONF_USER_POOL_ID,
    DATA_CLOUD,
    DATA_PLATFORMS_SETUP,
    DOMAIN,
    MODE_DEV,
    MODE_PROD,
)
from .prefs import CloudPreferences
from .repairs import async_manage_legacy_subscription_issue
from .subscription import async_subscription_info

DEFAULT_MODE = MODE_PROD

PLATFORMS = [Platform.BINARY_SENSOR, Platform.STT, Platform.TTS]

SERVICE_REMOTE_CONNECT = "remote_connect"
SERVICE_REMOTE_DISCONNECT = "remote_disconnect"

SIGNAL_CLOUD_CONNECTION_STATE: SignalType[CloudConnectionState] = SignalType(
    "CLOUD_CONNECTION_STATE"
)

STARTUP_REPAIR_DELAY = 1  # 1 hour

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
                vol.Optional(CONF_ALEXA): ALEXA_SCHEMA,
                vol.Optional(CONF_GOOGLE_ACTIONS): GACTIONS_SCHEMA,
                vol.Optional(CONF_ACCOUNT_LINK_SERVER): str,
                vol.Optional(CONF_ACCOUNTS_SERVER): str,
                vol.Optional(CONF_ACME_SERVER): str,
                vol.Optional(CONF_ALEXA_SERVER): str,
                vol.Optional(CONF_CLOUDHOOK_SERVER): str,
                vol.Optional(CONF_RELAYER_SERVER): str,
                vol.Optional(CONF_REMOTESTATE_SERVER): str,
                vol.Optional(CONF_THINGTALK_SERVER): str,
                vol.Optional(CONF_SERVICEHANDLERS_SERVER): str,
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
    return DATA_CLOUD in hass.data and hass.data[DATA_CLOUD].is_logged_in


@bind_hass
@callback
def async_is_connected(hass: HomeAssistant) -> bool:
    """Test if connected to the cloud."""
    return DATA_CLOUD in hass.data and hass.data[DATA_CLOUD].iot.connected


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
    return async_is_logged_in(hass) and not hass.data[DATA_CLOUD].subscription_expired


async def async_get_or_create_cloudhook(hass: HomeAssistant, webhook_id: str) -> str:
    """Get or create a cloudhook."""
    if not async_is_connected(hass):
        raise CloudNotConnected

    if not async_is_logged_in(hass):
        raise CloudNotAvailable

    cloud = hass.data[DATA_CLOUD]
    cloudhooks = cloud.client.cloudhooks
    if hook := cloudhooks.get(webhook_id):
        return cast(str, hook["cloudhook_url"])

    return await async_create_cloudhook(hass, webhook_id)


@bind_hass
async def async_create_cloudhook(hass: HomeAssistant, webhook_id: str) -> str:
    """Create a cloudhook."""
    if not async_is_connected(hass):
        raise CloudNotConnected

    if not async_is_logged_in(hass):
        raise CloudNotAvailable

    cloud = hass.data[DATA_CLOUD]
    hook = await cloud.cloudhooks.async_create(webhook_id, True)
    cloudhook_url: str = hook["cloudhook_url"]
    return cloudhook_url


@bind_hass
async def async_delete_cloudhook(hass: HomeAssistant, webhook_id: str) -> None:
    """Delete a cloudhook."""
    if DATA_CLOUD not in hass.data:
        raise CloudNotAvailable

    await hass.data[DATA_CLOUD].cloudhooks.async_delete(webhook_id)


@bind_hass
@callback
def async_remote_ui_url(hass: HomeAssistant) -> str:
    """Get the remote UI URL."""
    if not async_is_logged_in(hass):
        raise CloudNotAvailable

    if not hass.data[DATA_CLOUD].client.prefs.remote_enabled:
        raise CloudNotAvailable

    if not (remote_domain := hass.data[DATA_CLOUD].client.prefs.remote_domain):
        raise CloudNotAvailable

    return f"https://{remote_domain}"


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
    cloud = hass.data[DATA_CLOUD] = Cloud(client, **kwargs)

    async def _shutdown(event: Event) -> None:
        """Shutdown event."""
        await cloud.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)

    _remote_handle_prefs_updated(cloud)
    _setup_services(hass, prefs)

    async def async_startup_repairs(_: datetime) -> None:
        """Create repair issues after startup."""
        if not cloud.is_logged_in:
            return

        if subscription_info := await async_subscription_info(cloud):
            async_manage_legacy_subscription_issue(hass, subscription_info)

    loaded = False
    stt_platform_loaded = asyncio.Event()
    tts_platform_loaded = asyncio.Event()
    stt_tts_entities_added = asyncio.Event()
    hass.data[DATA_PLATFORMS_SETUP] = {
        Platform.STT: stt_platform_loaded,
        Platform.TTS: tts_platform_loaded,
        "stt_tts_entities_added": stt_tts_entities_added,
    }

    async def _on_start() -> None:
        """Handle cloud started after login."""
        nonlocal loaded

        # Prevent multiple discovery
        if loaded:
            return
        loaded = True

        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SYSTEM}
        )

    async def _on_connect() -> None:
        """Handle cloud connect."""
        async_dispatcher_send(
            hass, SIGNAL_CLOUD_CONNECTION_STATE, CloudConnectionState.CLOUD_CONNECTED
        )

    async def _on_disconnect() -> None:
        """Handle cloud disconnect."""
        async_dispatcher_send(
            hass, SIGNAL_CLOUD_CONNECTION_STATE, CloudConnectionState.CLOUD_DISCONNECTED
        )

    async def _on_initialized() -> None:
        """Update preferences."""
        await prefs.async_update(remote_domain=cloud.remote.instance_domain)

    cloud.register_on_start(_on_start)
    cloud.iot.register_on_connect(_on_connect)
    cloud.iot.register_on_disconnect(_on_disconnect)
    cloud.register_on_initialized(_on_initialized)

    await cloud.initialize()
    http_api.async_setup(hass)

    account_link.async_setup(hass)

    # Load legacy tts platform for backwards compatibility.
    hass.async_create_task(
        async_load_platform(
            hass,
            Platform.TTS,
            DOMAIN,
            {"platform_loaded": tts_platform_loaded},
            config,
        ),
        eager_start=True,
    )

    async_call_later(
        hass=hass,
        delay=timedelta(hours=STARTUP_REPAIR_DELAY),
        action=HassJob(
            async_startup_repairs, "cloud startup repairs", cancel_on_shutdown=True
        ),
    )

    return True


@callback
def _remote_handle_prefs_updated(cloud: Cloud[CloudClient]) -> None:
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    stt_tts_entities_added = hass.data[DATA_PLATFORMS_SETUP]["stt_tts_entities_added"]
    stt_tts_entities_added.set()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@callback
def _setup_services(hass: HomeAssistant, prefs: CloudPreferences) -> None:
    """Set up services for cloud component."""

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
