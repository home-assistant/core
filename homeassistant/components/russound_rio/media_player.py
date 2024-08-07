"""Support for Russound multizone controllers using RIO Protocol."""

from __future__ import annotations

import logging

from aiorussound import Source, Zone

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import RussoundConfigEntry
from .const import DOMAIN, MP_FEATURES_BY_FLAG

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

    # Discover controllers
    controllers = await russ.enumerate_controllers()

    entities = []
    for controller in controllers.values():
        sources = controller.sources
        for source in sources.values():
            await source.watch()
        for zone in controller.zones.values():
            await zone.watch()
            mp = RussoundZoneDevice(zone, sources)
            entities.append(mp)

    @callback
    def on_stop(event):
        """Shutdown cleanly when hass stops."""
        hass.loop.create_task(russ.close())

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_stop)

    async_add_entities(entities)


class RussoundZoneDevice(MediaPlayerEntity):
    """Representation of a Russound Zone."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_media_content_type = MediaType.MUSIC
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, zone: Zone, sources: dict[int, Source]) -> None:
        """Initialize the zone device."""
        self._controller = zone.controller
        self._zone = zone
        self._sources = sources
        self._attr_name = zone.name
        self._attr_unique_id = f"{self._controller.mac_address}-{zone.device_str()}"
        self._attr_device_info = DeviceInfo(
            # Use MAC address of Russound device as identifier
            identifiers={(DOMAIN, self._controller.mac_address)},
            connections={(CONNECTION_NETWORK_MAC, self._controller.mac_address)},
            manufacturer="Russound",
            name=self._controller.controller_type,
            model=self._controller.controller_type,
            sw_version=self._controller.firmware_version,
        )
        if self._controller.parent_controller:
            self._attr_device_info["via_device"] = (
                DOMAIN,
                self._controller.parent_controller.mac_address,
            )
        for flag, feature in MP_FEATURES_BY_FLAG.items():
            if flag in zone.instance.supported_features:
                self._attr_supported_features |= feature

    def _callback_handler(self, device_str, *args):
        if (
            device_str == self._zone.device_str()
            or device_str == self._current_source().device_str()
        ):
            self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callback handlers."""
        self._zone.add_callback(self._callback_handler)

    def _current_source(self) -> Source:
        return self._zone.fetch_current_source()

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        status = self._zone.status
        if status == "ON":
            return MediaPlayerState.ON
        if status == "OFF":
            return MediaPlayerState.OFF
        return None

    @property
    def source(self):
        """Get the currently selected source."""
        return self._current_source().name

    @property
    def source_list(self):
        """Return a list of available input sources."""
        return [x.name for x in self._sources.values()]

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._current_source().song_name

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._current_source().artist_name

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._current_source().album_name

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._current_source().cover_art_url

    @property
    def volume_level(self):
        """Volume level of the media player (0..1).

        Value is returned based on a range (0..50).
        Therefore float divide by 50 to get to the required range.
        """
        return float(self._zone.volume or "0") / 50.0

    async def async_turn_off(self) -> None:
        """Turn off the zone."""
        await self._zone.zone_off()

    async def async_turn_on(self) -> None:
        """Turn on the zone."""
        await self._zone.zone_on()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        rvol = int(volume * 50.0)
        await self._zone.set_volume(rvol)

    async def async_select_source(self, source: str) -> None:
        """Select the source input for this zone."""
        for source_id, src in self._sources.items():
            if src.name.lower() != source.lower():
                continue
            await self._zone.select_source(source_id)
            break

    async def async_volume_up(self) -> None:
        """Step the volume up."""
        await self._zone.volume_up()

    async def async_volume_down(self) -> None:
        """Step the volume down."""
        await self._zone.volume_down()
