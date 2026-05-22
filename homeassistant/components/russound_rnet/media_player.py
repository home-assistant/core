"""Support for interfacing with Russound via RNET Protocol."""

import asyncio
from collections.abc import Callable, Coroutine
import contextlib
import logging
import math
from typing import Any

from aiorussound.rnet.client import RussoundRNETClient
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import RussoundRNETConfigEntry
from .const import CONF_SOURCES, CONF_ZONES, DOMAIN, RNET_EXCEPTIONS, TYPE_TCP
from .repairs import async_create_deprecated_yaml_issue, async_create_yaml_import_issue

_LOGGER = logging.getLogger(__name__)

ZONE_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

SOURCE_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required("zones"): vol.Schema({cv.positive_int: ZONE_SCHEMA}),
        vol.Required("sources"): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
    }
)

PARALLEL_UPDATES = 0

# Max volume level on RNET devices
_MAX_VOLUME = 50


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Russound RNET platform from YAML (triggers repair-based import)."""
    from homeassistant.setup import async_setup_component  # noqa: PLC0415

    await async_setup_component(hass, DOMAIN, {})

    # Check if a config entry already exists for this host/port
    host = config.get(CONF_HOST, "")
    port = config.get(CONF_PORT, 0)
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (
            entry.data.get(CONF_TYPE) == TYPE_TCP
            and entry.data.get(CONF_HOST) == host
            and entry.data.get(CONF_PORT) == port
        ):
            # Config entry exists — tell user to remove YAML
            async_create_deprecated_yaml_issue(hass)
            return

    # No config entry — create fixable repair to complete import
    async_create_yaml_import_issue(hass, dict(config))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RussoundRNETConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Russound RNET media player from a config entry."""
    client = entry.runtime_data
    sources_config = entry.data.get(CONF_SOURCES, {})
    zones_config = entry.data.get(CONF_ZONES, {})

    # Build source list: sparse dict {"1": "Sonos", "3": "Radio"} → sorted tuples
    source_list = [
        name
        for _, name in sorted(
            ((int(k), v) for k, v in sources_config.items()), key=lambda x: x[0]
        )
    ]

    lock = asyncio.Lock()
    entities: list[RussoundRNETDevice] = []

    for zone_key, zone_name in zones_config.items():
        controller_id, zone_id = (int(x) for x in zone_key.split("_"))
        entities.append(
            RussoundRNETDevice(
                client,
                lock,
                source_list,
                zone_id,
                {CONF_NAME: zone_name},
                controller_id=controller_id,
                unique_id=f"{entry.entry_id}_{controller_id}_{zone_id}",
            )
        )

    async_add_entities(entities, True)


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
        controller_id: int | None = None,
        unique_id: str | None = None,
    ) -> None:
        """Initialise the Russound RNET device."""
        self._attr_name = extra[CONF_NAME]
        self._client = client
        self._lock = lock
        self._attr_source_list = sources
        self._attr_unique_id = unique_id
        if controller_id is not None:
            self._controller_id = controller_id
            self._zone_id = zone_id
        else:
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
