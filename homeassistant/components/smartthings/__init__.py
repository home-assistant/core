"""Support for SmartThings Cloud."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from aiohttp import ClientError
from pysmartthings import SmartThings
from pysmartthings.exceptions import SmartThingsAuthenticationFailedError

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .const import CONF_LOCATION_ID
from .coordinator import (
    SmartThingsConfigEntry,
    SmartThingsData,
    SmartThingsDeviceCoordinator,
)

_LOGGER = logging.getLogger(__name__)

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

    try:
        devices = await client.get_devices()
    except SmartThingsAuthenticationFailedError as err:
        raise ConfigEntryAuthFailed from err

    coordinators = [
        SmartThingsDeviceCoordinator(hass, entry, client, device) for device in devices
    ]

    await asyncio.gather(*[coordinator.async_refresh() for coordinator in coordinators])

    scenes = {
        scene.scene_id: scene
        for scene in await client.get_scenes(location_id=entry.data[CONF_LOCATION_ID])
    }

    entry.runtime_data = SmartThingsData(
        devices=[
            coordinator for coordinator in coordinators if coordinator.data is not None
        ],
        client=client,
        scenes=scenes,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SmartThingsConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
