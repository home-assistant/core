"""The motionEye integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
from http import HTTPStatus
import json
import logging
import os
from types import MappingProxyType
from typing import Any
from urllib.parse import urlencode, urljoin

from aiohttp.web import Request, Response
from motioneye_client.client import (
    MotionEyeClient,
    MotionEyeClientError,
    MotionEyeClientInvalidAuthError,
    MotionEyeClientPathError,
)
from motioneye_client.const import (
    KEY_CAMERAS,
    KEY_HTTP_METHOD_POST_JSON,
    KEY_ID,
    KEY_NAME,
    KEY_ROOT_DIRECTORY,
    KEY_WEB_HOOK_CONVERSION_SPECIFIERS,
    KEY_WEB_HOOK_CS_FILE_PATH,
    KEY_WEB_HOOK_CS_FILE_TYPE,
    KEY_WEB_HOOK_NOTIFICATIONS_ENABLED,
    KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD,
    KEY_WEB_HOOK_NOTIFICATIONS_URL,
    KEY_WEB_HOOK_STORAGE_ENABLED,
    KEY_WEB_HOOK_STORAGE_HTTP_METHOD,
    KEY_WEB_HOOK_STORAGE_URL,
)

from homeassistant.components.camera.const import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.media_source.const import URI_SCHEME
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.webhook import (
    async_generate_id,
    async_generate_path,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, ATTR_NAME, CONF_URL, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

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
    EVENT_FILE_URL,
    EVENT_MEDIA_CONTENT_ID,
    EVENT_MOTION_DETECTED,
    EVENT_MOTION_DETECTED_KEYS,
    MOTIONEYE_MANUFACTURER,
    SIGNAL_CAMERA_ADD,
    WEB_HOOK_SENTINEL_KEY,
    WEB_HOOK_SENTINEL_VALUE,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [CAMERA_DOMAIN, SENSOR_DOMAIN, SWITCH_DOMAIN]


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


def split_motioneye_device_identifier(
    identifier: tuple[str, str]
) -> tuple[str, str, int] | None:
    """Get the identifiers for a motionEye device."""
    if len(identifier) != 2 or identifier[0] != DOMAIN or "_" not in identifier[1]:
        return None
    config_id, camera_id_str = identifier[1].split("_", 1)
    try:
        camera_id = int(camera_id_str)
    except ValueError:
        return None
    return (DOMAIN, config_id, camera_id)


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
def async_generate_motioneye_webhook(
    hass: HomeAssistant, webhook_id: str
) -> str | None:
    """Generate the full local URL for a webhook_id."""
    try:
        return "{}{}".format(
            get_url(hass, allow_cloud=False),
            async_generate_path(webhook_id),
        )
    except NoURLAvailableError:
        _LOGGER.warning(
            "Unable to get Home Assistant URL. Have you set the internal and/or "
            "external URLs in Settings -> System -> Network?"
        )
        return None


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

        if url:
            set_motion_event = _set_webhook(
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
            )

            set_storage_event = _set_webhook(
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
            )
            if set_motion_event or set_storage_event:
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
        session=async_get_clientsession(hass),
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
    device_registry = dr.async_get(hass)

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
            status=HTTPStatus.BAD_REQUEST,
        )

    for key in (ATTR_DEVICE_ID, ATTR_EVENT_TYPE):
        if key not in data:
            return Response(
                text=f"Missing webhook parameter: {key}",
                status=HTTPStatus.BAD_REQUEST,
            )

    event_type = data[ATTR_EVENT_TYPE]
    device_registry = dr.async_get(hass)
    device_id = data[ATTR_DEVICE_ID]

    if not (device := device_registry.async_get(device_id)):
        return Response(
            text=f"Device not found: {device_id}",
            status=HTTPStatus.BAD_REQUEST,
        )

    if KEY_WEB_HOOK_CS_FILE_PATH in data and KEY_WEB_HOOK_CS_FILE_TYPE in data:
        try:
            event_file_type = int(data[KEY_WEB_HOOK_CS_FILE_TYPE])
        except ValueError:
            pass
        else:
            data.update(
                _get_media_event_data(
                    hass,
                    device,
                    data[KEY_WEB_HOOK_CS_FILE_PATH],
                    event_file_type,
                )
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


def _get_media_event_data(
    hass: HomeAssistant,
    device: dr.DeviceEntry,
    event_file_path: str,
    event_file_type: int,
) -> dict[str, str]:
    config_entry_id = next(iter(device.config_entries), None)
    if not config_entry_id or config_entry_id not in hass.data[DOMAIN]:
        return {}

    config_entry_data = hass.data[DOMAIN][config_entry_id]
    client = config_entry_data[CONF_CLIENT]
    coordinator = config_entry_data[CONF_COORDINATOR]

    for identifier in device.identifiers:
        data = split_motioneye_device_identifier(identifier)
        if data is not None:
            camera_id = data[2]
            camera = get_camera_from_cameras(camera_id, coordinator.data)
            break
    else:
        return {}

    root_directory = camera.get(KEY_ROOT_DIRECTORY) if camera else None
    if root_directory is None:
        return {}

    kind = "images" if client.is_file_type_image(event_file_type) else "movies"

    # The file_path in the event is the full local filesystem path to the
    # media. To convert that to the media path that motionEye will
    # understand, we need to strip the root directory from the path.
    if os.path.commonprefix([root_directory, event_file_path]) != root_directory:
        return {}

    file_path = "/" + os.path.relpath(event_file_path, root_directory)
    output = {
        EVENT_MEDIA_CONTENT_ID: (
            f"{URI_SCHEME}{DOMAIN}/{config_entry_id}#{device.id}#{kind}#{file_path}"
        ),
    }
    url = get_media_url(
        client,
        camera_id,
        file_path,
        kind == "images",
    )
    if url:
        output[EVENT_FILE_URL] = url
    return output


def get_media_url(
    client: MotionEyeClient, camera_id: int, path: str, image: bool
) -> str | None:
    """Get the URL for a motionEye media item."""
    with contextlib.suppress(MotionEyeClientPathError):
        if image:
            return client.get_image_url(camera_id, path)
        return client.get_movie_url(camera_id, path)
    return None


class MotionEyeEntity(CoordinatorEntity):
    """Base class for motionEye entities."""

    def __init__(
        self,
        config_entry_id: str,
        type_name: str,
        camera: dict[str, Any],
        client: MotionEyeClient,
        coordinator: DataUpdateCoordinator,
        options: MappingProxyType[str, Any],
        entity_description: EntityDescription = None,
    ) -> None:
        """Initialize a motionEye entity."""
        self._camera_id = camera[KEY_ID]
        self._device_identifier = get_motioneye_device_identifier(
            config_entry_id, self._camera_id
        )
        self._unique_id = get_motioneye_entity_unique_id(
            config_entry_id,
            self._camera_id,
            type_name,
        )
        self._client = client
        self._camera: dict[str, Any] | None = camera
        self._options = options
        if entity_description is not None:
            self.entity_description = entity_description
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        """Return a unique id for this instance."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(identifiers={self._device_identifier})

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._camera is not None and super().available
