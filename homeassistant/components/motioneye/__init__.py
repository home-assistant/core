"""The motionEye integration."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable
from urllib.parse import urlencode, urljoin

from aiohttp.web import Request, Response
from motioneye_client.client import (
    MotionEyeClient,
    MotionEyeClientError,
    MotionEyeClientInvalidAuthError,
)
from motioneye_client.const import (
    KEY_CAMERAS,
    KEY_HTTP_METHOD_POST_JSON,
    KEY_ID,
    KEY_NAME,
    KEY_WEB_HOOK_CONVERSION_SPECIFIERS,
    KEY_WEB_HOOK_NOTIFICATIONS_ENABLED,
    KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD,
    KEY_WEB_HOOK_NOTIFICATIONS_URL,
    KEY_WEB_HOOK_STORAGE_ENABLED,
    KEY_WEB_HOOK_STORAGE_HTTP_METHOD,
    KEY_WEB_HOOK_STORAGE_URL,
)

from homeassistant.components.camera.const import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.webhook import (
    async_generate_id,
    async_generate_path,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_NAME,
    CONF_URL,
    CONF_WEBHOOK_ID,
    HTTP_BAD_REQUEST,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.network import get_url
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_EVENT_TYPE,
    ATTR_WEBHOOK_ID,
    CONF_ADMIN_PASSWORD,
    CONF_ADMIN_USERNAME,
    CONF_CLIENT,
    CONF_COORDINATOR,
    CONF_SURVEILLANCE_PASSWORD,
    CONF_SURVEILLANCE_USERNAME,
    CONF_WEBHOOK_SET,
    CONF_WEBHOOK_SET_OVERWRITE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WEBHOOK_SET,
    DEFAULT_WEBHOOK_SET_OVERWRITE,
    DOMAIN,
    EVENT_FILE_STORED,
    EVENT_FILE_STORED_KEYS,
    EVENT_MOTION_DETECTED,
    EVENT_MOTION_DETECTED_KEYS,
    MOTIONEYE_MANUFACTURER,
    SIGNAL_CAMERA_ADD,
    WEB_HOOK_SENTINEL_KEY,
    WEB_HOOK_SENTINEL_VALUE,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [CAMERA_DOMAIN]


def create_motioneye_client(
    *args: Any,
    **kwargs: Any,
) -> MotionEyeClient:
    """Create a MotionEyeClient."""
    return MotionEyeClient(*args, **kwargs)


def get_motioneye_device_identifier(
    config_entry_id: str, camera_id: int
) -> tuple[str, str]:
    """Get the identifiers for a motionEye device."""
    return (DOMAIN, f"{config_entry_id}_{camera_id}")


def get_motioneye_entity_unique_id(
    config_entry_id: str, camera_id: int, entity_type: str
) -> str:
    """Get the unique_id for a motionEye entity."""
    return f"{config_entry_id}_{camera_id}_{entity_type}"


def get_camera_from_cameras(
    camera_id: int, data: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Get an individual camera dict from a multiple cameras data response."""
    for camera in data.get(KEY_CAMERAS, []) if data else []:
        if camera.get(KEY_ID) == camera_id:
            val: dict[str, Any] = camera
            return val
    return None


def is_acceptable_camera(camera: dict[str, Any] | None) -> bool:
    """Determine if a camera dict is acceptable."""
    return bool(camera and KEY_ID in camera and KEY_NAME in camera)


@callback
def listen_for_new_cameras(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_func: Callable,
) -> None:
    """Listen for new cameras."""

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_CAMERA_ADD.format(entry.entry_id),
            add_func,
        )
    )


@callback
def async_generate_motioneye_webhook(hass: HomeAssistant, webhook_id: str) -> str:
    """Generate the full local URL for a webhook_id."""
    return "{}{}".format(
        get_url(hass, allow_cloud=False),
        async_generate_path(webhook_id),
    )


@callback
def _add_camera(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MotionEyeClient,
    entry: ConfigEntry,
    camera_id: int,
    camera: dict[str, Any],
    device_identifier: tuple[str, str],
) -> None:
    """Add a motionEye camera to hass."""

    def _is_recognized_web_hook(url: str) -> bool:
        """Determine whether this integration set a web hook."""
        return f"{WEB_HOOK_SENTINEL_KEY}={WEB_HOOK_SENTINEL_VALUE}" in url

    def _set_webhook(
        url: str,
        key_url: str,
        key_method: str,
        key_enabled: str,
        camera: dict[str, Any],
    ) -> bool:
        """Set a web hook."""
        if (
            entry.options.get(
                CONF_WEBHOOK_SET_OVERWRITE,
                DEFAULT_WEBHOOK_SET_OVERWRITE,
            )
            or not camera.get(key_url)
            or _is_recognized_web_hook(camera[key_url])
        ) and (
            not camera.get(key_enabled, False)
            or camera.get(key_method) != KEY_HTTP_METHOD_POST_JSON
            or camera.get(key_url) != url
        ):
            camera[key_enabled] = True
            camera[key_method] = KEY_HTTP_METHOD_POST_JSON
            camera[key_url] = url
            return True
        return False

    def _build_url(
        device: dr.DeviceEntry, base: str, event_type: str, keys: list[str]
    ) -> str:
        """Build a motionEye webhook URL."""

        # This URL-surgery cannot use YARL because the output must NOT be
        # url-encoded. This is because motionEye will do further string
        # manipulation/substitution on this value before ultimately fetching it,
        # and it cannot deal with URL-encoded input to that string manipulation.
        return urljoin(
            base,
            "?"
            + urlencode(
                {
                    **{k: KEY_WEB_HOOK_CONVERSION_SPECIFIERS[k] for k in sorted(keys)},
                    WEB_HOOK_SENTINEL_KEY: WEB_HOOK_SENTINEL_VALUE,
                    ATTR_EVENT_TYPE: event_type,
                    ATTR_DEVICE_ID: device.id,
                },
                safe="%{}",
            ),
        )

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={device_identifier},
        manufacturer=MOTIONEYE_MANUFACTURER,
        model=MOTIONEYE_MANUFACTURER,
        name=camera[KEY_NAME],
    )
    if entry.options.get(CONF_WEBHOOK_SET, DEFAULT_WEBHOOK_SET):
        url = async_generate_motioneye_webhook(hass, entry.data[CONF_WEBHOOK_ID])

        if _set_webhook(
            _build_url(
                device,
                url,
                EVENT_MOTION_DETECTED,
                EVENT_MOTION_DETECTED_KEYS,
            ),
            KEY_WEB_HOOK_NOTIFICATIONS_URL,
            KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD,
            KEY_WEB_HOOK_NOTIFICATIONS_ENABLED,
            camera,
        ) | _set_webhook(
            _build_url(
                device,
                url,
                EVENT_FILE_STORED,
                EVENT_FILE_STORED_KEYS,
            ),
            KEY_WEB_HOOK_STORAGE_URL,
            KEY_WEB_HOOK_STORAGE_HTTP_METHOD,
            KEY_WEB_HOOK_STORAGE_ENABLED,
            camera,
        ):
            hass.async_create_task(client.async_set_camera(camera_id, camera))

    async_dispatcher_send(
        hass,
        SIGNAL_CAMERA_ADD.format(entry.entry_id),
        camera,
    )


async def _async_entry_updated(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle entry updates."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up motionEye from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = create_motioneye_client(
        entry.data[CONF_URL],
        admin_username=entry.data.get(CONF_ADMIN_USERNAME),
        admin_password=entry.data.get(CONF_ADMIN_PASSWORD),
        surveillance_username=entry.data.get(CONF_SURVEILLANCE_USERNAME),
        surveillance_password=entry.data.get(CONF_SURVEILLANCE_PASSWORD),
    )

    try:
        await client.async_client_login()
    except MotionEyeClientInvalidAuthError as exc:
        await client.async_client_close()
        raise ConfigEntryAuthFailed from exc
    except MotionEyeClientError as exc:
        await client.async_client_close()
        raise ConfigEntryNotReady from exc

    # Ensure every loaded entry has a registered webhook id.
    if CONF_WEBHOOK_ID not in entry.data:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_WEBHOOK_ID: async_generate_id()}
        )
    webhook_register(
        hass, DOMAIN, "motionEye", entry.data[CONF_WEBHOOK_ID], handle_webhook
    )

    @callback
    async def async_update_data() -> dict[str, Any] | None:
        try:
            return await client.async_get_cameras()
        except MotionEyeClientError as exc:
            raise UpdateFailed("Error communicating with API") from exc

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_CLIENT: client,
        CONF_COORDINATOR: coordinator,
    }

    current_cameras: set[tuple[str, str]] = set()
    device_registry = await dr.async_get_registry(hass)

    @callback
    def _async_process_motioneye_cameras() -> None:
        """Process motionEye camera additions and removals."""
        inbound_camera: set[tuple[str, str]] = set()
        if coordinator.data is None or KEY_CAMERAS not in coordinator.data:
            return

        for camera in coordinator.data[KEY_CAMERAS]:
            if not is_acceptable_camera(camera):
                return
            camera_id = camera[KEY_ID]
            device_identifier = get_motioneye_device_identifier(
                entry.entry_id, camera_id
            )
            inbound_camera.add(device_identifier)

            if device_identifier in current_cameras:
                continue
            current_cameras.add(device_identifier)
            _add_camera(
                hass,
                device_registry,
                client,
                entry,
                camera_id,
                camera,
                device_identifier,
            )

        # Ensure every device associated with this config entry is still in the
        # list of motionEye cameras, otherwise remove the device (and thus
        # entities).
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            for identifier in device_entry.identifiers:
                if identifier in inbound_camera:
                    break
            else:
                device_registry.async_remove_device(device_entry.id)

    async def setup_then_listen() -> None:
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_setup(entry, platform)
                for platform in PLATFORMS
            )
        )
        entry.async_on_unload(
            coordinator.async_add_listener(_async_process_motioneye_cameras)
        )
        await coordinator.async_refresh()
        entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    hass.async_create_task(setup_then_listen())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        config_data = hass.data[DOMAIN].pop(entry.entry_id)
        await config_data[CONF_CLIENT].async_client_close()

    return unload_ok


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: Request
) -> None | Response:
    """Handle webhook callback."""

    try:
        data = await request.json()
    except (json.decoder.JSONDecodeError, UnicodeDecodeError):
        return Response(
            text="Could not decode request",
            status=HTTP_BAD_REQUEST,
        )

    for key in (ATTR_DEVICE_ID, ATTR_EVENT_TYPE):
        if key not in data:
            return Response(
                text=f"Missing webhook parameter: {key}",
                status=HTTP_BAD_REQUEST,
            )

    event_type = data[ATTR_EVENT_TYPE]
    device_registry = dr.async_get(hass)
    device_id = data[ATTR_DEVICE_ID]
    device = device_registry.async_get(device_id)

    if not device:
        return Response(
            text=f"Device not found: {device_id}",
            status=HTTP_BAD_REQUEST,
        )

    hass.bus.async_fire(
        f"{DOMAIN}.{event_type}",
        {
            ATTR_DEVICE_ID: device.id,
            ATTR_NAME: device.name,
            ATTR_WEBHOOK_ID: webhook_id,
            **data,
        },
    )
    return None
