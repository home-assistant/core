"""UniFi Protect Integration utils."""

from __future__ import annotations

from collections.abc import Generator, Iterable
import contextlib
from pathlib import Path
import socket
from typing import TYPE_CHECKING

from aiohttp import CookieJar
from uiprotect import ProtectApiClient
from uiprotect.data import (
    Bootstrap,
    CameraChannel,
    Light,
    LightModeEnableType,
    LightModeType,
    ProtectAdoptableDeviceModel,
)

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_ALL_UPDATES,
    CONF_OVERRIDE_CHOST,
    DEVICES_FOR_SUBSCRIBE,
    ModelType,
)

if TYPE_CHECKING:
    from .data import UFPConfigEntry


@callback
def _async_unifi_mac_from_hass(mac: str) -> str:
    # MAC addresses in UFP are always caps
    return mac.replace(":", "").upper()


@callback
def _async_short_mac(mac: str) -> str:
    """Get the short mac address from the full mac."""
    return _async_unifi_mac_from_hass(mac)[-6:]


async def _async_resolve(hass: HomeAssistant, host: str) -> str | None:
    """Resolve a hostname to an ip."""
    with contextlib.suppress(OSError):
        return next(
            iter(
                raw[0]
                for family, _, _, _, raw in await hass.loop.getaddrinfo(
                    host, None, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
                )
                if family == socket.AF_INET
            ),
            None,
        )
    return None


@callback
def async_get_devices_by_type(
    bootstrap: Bootstrap, device_type: ModelType
) -> dict[str, ProtectAdoptableDeviceModel]:
    """Get devices by type."""
    devices: dict[str, ProtectAdoptableDeviceModel]
    devices = getattr(bootstrap, device_type.devices_key)
    return devices


@callback
def async_get_devices(
    bootstrap: Bootstrap, model_type: Iterable[ModelType]
) -> Generator[ProtectAdoptableDeviceModel]:
    """Return all device by type."""
    return (
        device
        for device_type in model_type
        for device in async_get_devices_by_type(bootstrap, device_type).values()
    )


@callback
def async_get_light_motion_current(obj: Light) -> str:
    """Get light motion mode for Flood Light."""

    if (
        obj.light_mode_settings.mode is LightModeType.MOTION
        and obj.light_mode_settings.enable_at is LightModeEnableType.DARK
    ):
        return f"{LightModeType.MOTION.value}Dark"
    return obj.light_mode_settings.mode.value


@callback
def async_create_api_client(
    hass: HomeAssistant, entry: UFPConfigEntry
) -> ProtectApiClient:
    """Create ProtectApiClient from config entry."""

    session = async_create_clientsession(hass, cookie_jar=CookieJar(unsafe=True))
    return ProtectApiClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        session=session,
        subscribed_models=DEVICES_FOR_SUBSCRIBE,
        override_connection_host=entry.options.get(CONF_OVERRIDE_CHOST, False),
        ignore_stats=not entry.options.get(CONF_ALL_UPDATES, False),
        ignore_unadopted=False,
        cache_dir=Path(hass.config.path(STORAGE_DIR, "unifiprotect")),
        config_dir=Path(hass.config.path(STORAGE_DIR, "unifiprotect")),
    )


@callback
def get_camera_base_name(channel: CameraChannel) -> str:
    """Get base name for cameras channel."""

    camera_name = channel.name
    if channel.name != "Package Camera":
        camera_name = f"{channel.name} resolution channel"

    return camera_name
