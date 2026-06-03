"""Kii Audio media player platform."""

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KiiAudioConfigEntry
from .const import KII_CONTROL_PRODUCT_ID, MAX_VOLUME, MIN_VOLUME, VOLUME_STEP
from .coordinator import KiiAudioCoordinator
from .entity import zone_device_info

SOURCE_NAMES = {
    "analog": "Analog",
    "digital": "Digital (Auto)",
    "digital_auto": "Digital (Auto)",
    "digital_xlr": "Digital (XLR)",
    "digital_kiilink": "Digital (KiiLink)",
    "dante": "Dante",
    "bluetooth": "Bluetooth Stream",
    "spotify": "Spotify Connect",
    "tidal": "Tidal Connect",
    "qobuzconnect": "Qobuz Connect",
    "airplay": "AirPlay",
    "roon": "Roon",
    "VTuner": "vTuner",
    "airableRadios": "airable Radio",
    "airablePodcasts": "airable Podcasts",
    "tuneIn": "TuneIn",
    "control_usb": "USB",
    "control_coax": "Coax",
    "control_optical": "Optical",
    "control_bluetooth": "Bluetooth",
}


SPEAKER_SOURCES = [
    "analog",
    "digital_auto",
    "digital_xlr",
    "digital_kiilink",
    "dante",
]

CONTROLLER_SOURCES = [
    "control_coax",
    "control_optical",
    "control_usb",
    "control_bluetooth",
]

SPEAKER_SOURCES_WITH_CONTROLLER = [
    "analog",
    "digital_xlr",
    "dante",
]

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.SELECT_SOURCE
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: KiiAudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kii Audio media player entities."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        KiiAudioZoneMediaPlayer(coordinator, zone)
        for zone in coordinator.data.get("zones", [])
        if isinstance(zone, dict) and isinstance(zone.get("zoneId"), str)
    )


class KiiAudioZoneMediaPlayer(
    CoordinatorEntity[KiiAudioCoordinator], MediaPlayerEntity
):
    """Representation of a Kii Audio zone."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_volume_step = VOLUME_STEP / (MAX_VOLUME - MIN_VOLUME)

    def __init__(self, coordinator: KiiAudioCoordinator, zone: dict[str, Any]) -> None:
        """Initialize the zone media player."""
        super().__init__(coordinator)
        self._zone_id = zone["zoneId"]
        system_id = (
            coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        )
        self._attr_unique_id = f"{system_id}_{self._zone_id}"
        self._attr_device_info = zone_device_info(coordinator, self._zone_id, zone)

    @property
    def state(self) -> MediaPlayerState:
        """Return the zone state."""
        if self._settings.get("power") is False:
            return MediaPlayerState.OFF
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        """Return volume level, range 0..1."""
        volume = self._audio.get("volume")
        if isinstance(volume, bool) or not isinstance(volume, int | float):
            return None
        return max(
            0.0,
            min(1.0, (float(volume) - MIN_VOLUME) / (MAX_VOLUME - MIN_VOLUME)),
        )

    @property
    def is_volume_muted(self) -> bool | None:
        """Return whether the zone is muted."""
        mute = self._audio.get("mute")
        return mute if isinstance(mute, bool) else None

    async def async_set_volume_level(self, volume: float) -> None:
        """Request a zone volume change."""
        volume = max(0.0, min(1.0, volume))
        kii_volume = MIN_VOLUME + (volume * (MAX_VOLUME - MIN_VOLUME))
        await self.coordinator.async_set_zone_volume(
            self._zone_id, round(kii_volume, 1)
        )

    async def async_mute_volume(self, mute: bool) -> None:
        """Request a zone mute change."""
        await self.coordinator.async_set_zone_mute(self._zone_id, mute)

    @property
    def source(self) -> str | None:
        """Return the active source."""
        source = self._audio.get("source")
        if not isinstance(source, str):
            return None
        return SOURCE_NAMES.get(source, source)

    @property
    def source_list(self) -> list[str]:
        """Return selectable sources for the zone."""
        return [SOURCE_NAMES[source] for source in self._selectable_source_ids]

    async def async_select_source(self, source: str) -> None:
        """Request a zone source change."""
        source_id = self._selectable_source_ids_by_name.get(source, source)
        if source_id not in self._selectable_source_ids:
            return
        await self.coordinator.async_set_zone_source(self._zone_id, source_id)

    async def async_volume_up(self) -> None:
        """Request a zone volume increase."""
        volume = self._audio.get("volume")
        if isinstance(volume, bool) or not isinstance(volume, int | float):
            return
        await self.coordinator.async_set_zone_volume(
            self._zone_id, min(MAX_VOLUME, float(volume) + VOLUME_STEP)
        )

    async def async_volume_down(self) -> None:
        """Request a zone volume decrease."""
        volume = self._audio.get("volume")
        if isinstance(volume, bool) or not isinstance(volume, int | float):
            return
        await self.coordinator.async_set_zone_volume(
            self._zone_id, max(MIN_VOLUME, float(volume) - VOLUME_STEP)
        )

    async def async_turn_on(self) -> None:
        """Request the zone to turn on."""
        await self.coordinator.async_set_zone_power(self._zone_id, True)

    async def async_turn_off(self) -> None:
        """Request the zone to turn off."""
        await self.coordinator.async_set_zone_power(self._zone_id, False)

    @property
    def _zone(self) -> dict[str, Any]:
        """Return the latest zone data."""
        zones = self.coordinator.data.get("zones", [])
        for zone in zones:
            if isinstance(zone, dict) and zone.get("zoneId") == self._zone_id:
                return zone
        return {}

    @property
    def _settings(self) -> dict[str, Any]:
        """Return the latest zone settings."""
        settings = self._zone.get("settings")
        return settings if isinstance(settings, dict) else {}

    @property
    def _audio(self) -> dict[str, Any]:
        """Return the latest zone audio settings."""
        audio = self._settings.get("audio")
        return audio if isinstance(audio, dict) else {}

    @property
    def _selectable_source_ids(self) -> list[str]:
        """Return source ids that the user may select for this zone."""
        if self._has_kii_control:
            return CONTROLLER_SOURCES + SPEAKER_SOURCES_WITH_CONTROLLER
        return SPEAKER_SOURCES

    @property
    def _selectable_source_ids_by_name(self) -> dict[str, str]:
        """Return display labels mapped to selectable source ids."""
        return {
            SOURCE_NAMES[source_id]: source_id
            for source_id in self._selectable_source_ids
        }

    @property
    def _has_kii_control(self) -> bool:
        """Return whether this zone has a Kii Control device."""
        kiilink = self._zone.get("kiilink")
        if not isinstance(kiilink, dict):
            return False
        devices = kiilink.get("devices")
        if not isinstance(devices, list):
            return False
        return any(
            isinstance(device, dict)
            and device.get("productId") == KII_CONTROL_PRODUCT_ID
            for device in devices
        )
