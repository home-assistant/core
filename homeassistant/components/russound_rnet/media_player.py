"""Support for interfacing with Russound via RNET Protocol."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import contextlib
import logging
import math
from typing import Any

from aiorussound import RussoundTcpConnectionHandler
from aiorussound.exceptions import CommandError
from aiorussound.rnet.client import RussoundRNETClient
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_ZONES = "zones"
CONF_SOURCES = "sources"

RNET_EXCEPTIONS = (
    CommandError,
    ConnectionRefusedError,
    TimeoutError,
    asyncio.IncompleteReadError,
    OSError,
)

ZONE_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

SOURCE_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_ZONES): vol.Schema({cv.positive_int: ZONE_SCHEMA}),
        vol.Required(CONF_SOURCES): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
    }
)

# Max volume level on RNET devices
_MAX_VOLUME = 50


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Russound RNET platform."""
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    client = RussoundRNETClient(RussoundTcpConnectionHandler(host, port))
    try:
        await client.connect()
    except RNET_EXCEPTIONS as err:
        raise PlatformNotReady(
            f"Could not connect to Russound RNET at {host}:{port}"
        ) from err

    sources = [source[CONF_NAME] for source in config[CONF_SOURCES]]
    lock = asyncio.Lock()

    async def _async_disconnect(*_: Any) -> None:
        """Disconnect the RNET client on HA shutdown."""
        with contextlib.suppress(*RNET_EXCEPTIONS):
            await client.disconnect()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect)

    async_add_entities(
        [
            RussoundRNETDevice(client, lock, sources, zone_id, extra)
            for zone_id, extra in config[CONF_ZONES].items()
        ],
        True,
    )


class RussoundRNETDevice(MediaPlayerEntity):
    """Representation of a Russound RNET device."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(
        self,
        client: RussoundRNETClient,
        lock: asyncio.Lock,
        sources: list[str],
        zone_id: int,
        extra: dict[str, str],
    ) -> None:
        """Initialise the Russound RNET device."""
        self._attr_name = extra[CONF_NAME]
        self._client = client
        self._lock = lock
        self._attr_source_list = sources
        self._controller_id = math.ceil(zone_id / 6)
        self._zone_id = (zone_id - 1) % 6 + 1

    async def _async_ensure_connected(self) -> None:
        """Ensure the client is connected, reconnecting if needed."""
        if not self._client.is_connected:
            _LOGGER.debug("Reconnecting RNET client")
            await self._client.connect()

    async def _async_run_with_retry(
        self, command: Callable[[], Coroutine[Any, Any, Any]]
    ) -> None:
        """Run a command with reconnect retry on failure."""
        async with self._lock:
            try:
                await self._async_ensure_connected()
                await command()
            except RNET_EXCEPTIONS:
                with contextlib.suppress(*RNET_EXCEPTIONS):
                    await self._client.disconnect()
                try:
                    await self._async_ensure_connected()
                    await command()
                except RNET_EXCEPTIONS:
                    _LOGGER.error(
                        "Command failed for zone %s on controller %s after retry",
                        self._zone_id,
                        self._controller_id,
                    )

    async def async_update(self) -> None:
        """Retrieve latest state."""
        async with self._lock:
            try:
                await self._async_ensure_connected()
                info = await self._client.get_all_zone_info(
                    self._controller_id, self._zone_id
                )
            except RNET_EXCEPTIONS:
                with contextlib.suppress(*RNET_EXCEPTIONS):
                    await self._client.disconnect()
                try:
                    await self._async_ensure_connected()
                    info = await self._client.get_all_zone_info(
                        self._controller_id, self._zone_id
                    )
                except RNET_EXCEPTIONS:
                    _LOGGER.error(
                        "Could not update zone %s on controller %s",
                        self._zone_id,
                        self._controller_id,
                    )
                    self._attr_available = False
                    return

        self._attr_available = True
        self._attr_state = MediaPlayerState.ON if info.power else MediaPlayerState.OFF
        self._attr_volume_level = info.volume / _MAX_VOLUME
        # info.source is 1-based; source_list is 0-based
        index = info.source - 1
        if self.source_list and 0 <= index < len(self.source_list):
            self._attr_source = self.source_list[index]

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level. Volume has a range (0..1)."""
        device_volume = max(0, min(_MAX_VOLUME, int(volume * _MAX_VOLUME)))
        await self._async_run_with_retry(
            lambda: self._client.set_volume(
                self._controller_id, self._zone_id, device_volume
            )
        )

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._async_run_with_retry(
            lambda: self._client.set_zone_power(
                self._controller_id, self._zone_id, True
            )
        )

    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await self._async_run_with_retry(
            lambda: self._client.set_zone_power(
                self._controller_id, self._zone_id, False
            )
        )

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""

        async def _mute_if_needed() -> None:
            if self.is_volume_muted != mute:
                await self._client.toggle_mute(self._controller_id, self._zone_id)

        await self._async_run_with_retry(_mute_if_needed)

    async def async_select_source(self, source: str) -> None:
        """Set the input source."""
        if self.source_list and source in self.source_list:
            # source_list is 0-based; RNET source is 1-based
            index = self.source_list.index(source) + 1
            await self._async_run_with_retry(
                lambda: self._client.select_source(
                    self._controller_id, self._zone_id, index
                )
            )
