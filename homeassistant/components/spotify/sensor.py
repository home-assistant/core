"""Sensor platform for Spotify."""

from collections.abc import Callable
from dataclasses import dataclass

from spotifyaio.models import AudioFeatures, Key

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SpotifyConfigEntry, SpotifyCoordinator
from .entity import SpotifyEntity


@dataclass(frozen=True, kw_only=True)
class SpotifyAudioFeaturesSensorEntityDescription(SensorEntityDescription):
    """Describes Spotify sensor entity."""

    value_fn: Callable[[AudioFeatures], float | str | None]


KEYS: dict[Key, str] = {
    Key.C: "C",
    Key.C_SHARP_D_FLAT: "C♯/D♭",
    Key.D: "D",
    Key.D_SHARP_E_FLAT: "D♯/E♭",
    Key.E: "E",
    Key.F: "F",
    Key.F_SHARP_G_FLAT: "F♯/G♭",
    Key.G: "G",
    Key.G_SHARP_A_FLAT: "G♯/A♭",
    Key.A: "A",
    Key.A_SHARP_B_FLAT: "A♯/B♭",
    Key.B: "B",
}

KEY_OPTIONS = list(KEYS.values())


def _get_key(audio_features: AudioFeatures) -> str | None:
    if audio_features.key is None:
        return None
    return KEYS[audio_features.key]


AUDIO_FEATURE_SENSORS: tuple[SpotifyAudioFeaturesSensorEntityDescription, ...] = (
    SpotifyAudioFeaturesSensorEntityDescription(
        key="bpm",
        translation_key="song_tempo",
        native_unit_of_measurement="bpm",
        suggested_display_precision=0,
        value_fn=lambda audio_features: audio_features.tempo,
    ),
    SpotifyAudioFeaturesSensorEntityDescription(
        key="danceability",
        translation_key="danceability",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda audio_features: audio_features.danceability * 100,
        entity_registry_enabled_default=False,
    ),
    SpotifyAudioFeaturesSensorEntityDescription(
        key="energy",
        translation_key="energy",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda audio_features: audio_features.energy * 100,
        entity_registry_enabled_default=False,
    ),
    SpotifyAudioFeaturesSensorEntityDescription(
        key="mode",
        translation_key="mode",
        device_class=SensorDeviceClass.ENUM,
        options=["major", "minor"],
        value_fn=lambda audio_features: audio_features.mode.name.lower(),
        entity_registry_enabled_default=False,
    ),
    SpotifyAudioFeaturesSensorEntityDescription(
        key="speechiness",
        translation_key="speechiness",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda audio_features: audio_features.speechiness * 100,
        entity_registry_enabled_default=False,
    ),
    SpotifyAudioFeaturesSensorEntityDescription(
        key="acousticness",
        translation_key="acousticness",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda audio_features: audio_features.acousticness * 100,
        entity_registry_enabled_default=False,
    ),
    SpotifyAudioFeaturesSensorEntityDescription(
        key="instrumentalness",
        translation_key="instrumentalness",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda audio_features: audio_features.instrumentalness * 100,
        entity_registry_enabled_default=False,
    ),
    SpotifyAudioFeaturesSensorEntityDescription(
        key="liveness",
        translation_key="liveness",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda audio_features: audio_features.liveness * 100,
        entity_registry_enabled_default=False,
    ),
    SpotifyAudioFeaturesSensorEntityDescription(
        key="valence",
        translation_key="valence",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda audio_features: audio_features.valence * 100,
        entity_registry_enabled_default=False,
    ),
    SpotifyAudioFeaturesSensorEntityDescription(
        key="time_signature",
        translation_key="time_signature",
        device_class=SensorDeviceClass.ENUM,
        options=["3/4", "4/4", "5/4", "6/4", "7/4"],
        value_fn=lambda audio_features: f"{audio_features.time_signature}/4",
        entity_registry_enabled_default=False,
    ),
    SpotifyAudioFeaturesSensorEntityDescription(
        key="key",
        translation_key="key",
        device_class=SensorDeviceClass.ENUM,
        options=KEY_OPTIONS,
        value_fn=_get_key,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpotifyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spotify sensor based on a config entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        SpotifyAudioFeatureSensor(coordinator, description)
        for description in AUDIO_FEATURE_SENSORS
    )


class SpotifyAudioFeatureSensor(SpotifyEntity, SensorEntity):
    """Representation of a Spotify sensor."""

    entity_description: SpotifyAudioFeaturesSensorEntityDescription

    def __init__(
        self,
        coordinator: SpotifyCoordinator,
        entity_description: SpotifyAudioFeaturesSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.current_user.user_id}_{entity_description.key}"
        )
        self.entity_description = entity_description

    @property
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""
        if (audio_features := self.coordinator.data.audio_features) is None:
            return None
        return self.entity_description.value_fn(audio_features)
