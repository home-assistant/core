"""Support for Russound multizone controllers using RIO Protocol."""

from __future__ import annotations

import logging

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import RussoundConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Russound RIO platform."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )
    if (
        result["type"] is FlowResultType.CREATE_ENTRY
        or result["reason"] == "single_instance_allowed"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2025.2.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Russound RIO",
            },
        )
        return
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_import_issue_{result['reason']}",
        breaks_in_ha_version="2025.2.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Russound RIO",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RussoundConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Russound RIO platform."""
    russ = entry.runtime_data

    # Discover sources and zones
    sources = await russ.enumerate_sources()
    valid_zones = await russ.enumerate_zones()

    entities = []
    for zone_id, name in valid_zones:
        if zone_id.controller > 6:
            _LOGGER.debug(
                "Zone ID %s exceeds RIO controller maximum, skipping",
                zone_id.device_str(),
            )
            continue
        await russ.watch_zone(zone_id)
        zone = RussoundZoneDevice(russ, zone_id, name, sources)
        entities.append(zone)

    @callback
    def on_stop(event):
        """Shutdown cleanly when hass stops."""
        hass.loop.create_task(russ.close())

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_stop)

    async_add_entities(entities)


class RussoundZoneDevice(MediaPlayerEntity):
    """Representation of a Russound Zone."""

    _attr_media_content_type = MediaType.MUSIC
    _attr_should_poll = False
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, russ, zone_id, name, sources) -> None:
        """Initialize the zone device."""
        super().__init__()
        self._name = name
        self._russ = russ
        self._zone_id = zone_id
        self._sources = sources

    def _zone_var(self, name, default=None):
        return self._russ.get_cached_zone_variable(self._zone_id, name, default)

    def _source_var(self, name, default=None):
        current = int(self._zone_var("currentsource", 0))
        if current:
            return self._russ.get_cached_source_variable(current, name, default)
        return default

    def _source_na_var(self, name):
        """Will replace invalid values with None."""
        current = int(self._zone_var("currentsource", 0))
        if current:
            value = self._russ.get_cached_source_variable(current, name, None)
            if value in (None, "", "------"):
                return None
            return value
        return None

    def _zone_callback_handler(self, zone_id, *args):
        if zone_id == self._zone_id:
            self.schedule_update_ha_state()

    def _source_callback_handler(self, source_id, *args):
        current = int(self._zone_var("currentsource", 0))
        if source_id == current:
            self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callback handlers."""
        self._russ.add_zone_callback(self._zone_callback_handler)
        self._russ.add_source_callback(self._source_callback_handler)

    @property
    def name(self):
        """Return the name of the zone."""
        return self._zone_var("name", self._name)

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        status = self._zone_var("status", "OFF")
        if status == "ON":
            return MediaPlayerState.ON
        if status == "OFF":
            return MediaPlayerState.OFF
        return None

    @property
    def source(self):
        """Get the currently selected source."""
        return self._source_na_var("name")

    @property
    def source_list(self):
        """Return a list of available input sources."""
        return [x[1] for x in self._sources]

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._source_na_var("songname")

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._source_na_var("artistname")

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._source_na_var("albumname")

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._source_na_var("coverarturl")

    @property
    def volume_level(self):
        """Volume level of the media player (0..1).

        Value is returned based on a range (0..50).
        Therefore float divide by 50 to get to the required range.
        """
        return float(self._zone_var("volume", 0)) / 50.0

    async def async_turn_off(self) -> None:
        """Turn off the zone."""
        await self._russ.send_zone_event(self._zone_id, "ZoneOff")

    async def async_turn_on(self) -> None:
        """Turn on the zone."""
        await self._russ.send_zone_event(self._zone_id, "ZoneOn")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        rvol = int(volume * 50.0)
        await self._russ.send_zone_event(self._zone_id, "KeyPress", "Volume", rvol)

    async def async_select_source(self, source: str) -> None:
        """Select the source input for this zone."""
        for source_id, name in self._sources:
            if name.lower() != source.lower():
                continue
            await self._russ.send_zone_event(self._zone_id, "SelectSource", source_id)
            break
