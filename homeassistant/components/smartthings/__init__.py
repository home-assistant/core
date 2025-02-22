"""Support for SmartThings Cloud."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from aiohttp import ClientError
from pysmartthings import (
    Attribute,
    Capability,
    Device,
    Scene,
    SmartThings,
    SmartThingsAuthenticationFailedError,
    Status,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .const import CONF_INSTALLED_APP_ID, CONF_LOCATION_ID

_LOGGER = logging.getLogger(__name__)


@dataclass
class SmartThingsData:
    """Define an object to hold SmartThings data."""

    devices: dict[str, FullDevice]
    scenes: dict[str, Scene]
    client: SmartThings


@dataclass
class FullDevice:
    """Define an object to hold device data."""

    device: Device
    status: dict[str, dict[Capability, dict[Attribute, Status]]]


type SmartThingsConfigEntry = ConfigEntry[SmartThingsData]

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SCENE,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: SmartThingsConfigEntry) -> bool:
    """Initialize config entry which represents an installed SmartApp."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)

    try:
        await session.async_ensure_token_valid()
    except ClientError as err:
        raise ConfigEntryNotReady from err

    client = SmartThings(session=async_get_clientsession(hass))

    async def _refresh_token() -> str:
        await session.async_ensure_token_valid()
        token = session.token[CONF_ACCESS_TOKEN]
        if TYPE_CHECKING:
            assert isinstance(token, str)
        return token

    client.refresh_token_function = _refresh_token

    device_status: dict[str, FullDevice] = {}
    try:
        devices = await client.get_devices()
        for device in devices:
            status = await client.get_device_status(device.device_id)
            device_status[device.device_id] = FullDevice(device=device, status=status)
    except SmartThingsAuthenticationFailedError as err:
        raise ConfigEntryAuthFailed from err

    scenes = {
        scene.scene_id: scene
        for scene in await client.get_scenes(location_id=entry.data[CONF_LOCATION_ID])
    }

    entry.runtime_data = SmartThingsData(
        devices=device_status,
        client=client,
        scenes=scenes,
    )

    hass.loop.create_task(
        client.subscribe(
            entry.data[CONF_LOCATION_ID], entry.data[CONF_TOKEN][CONF_INSTALLED_APP_ID]
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SmartThingsConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
