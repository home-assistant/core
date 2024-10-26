"""Sensor platform for Spotify."""

from collections.abc import Callable
from dataclasses import dataclass

from spotifyaio.models import AudioFeatures

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SpotifyConfigEntry, SpotifyCoordinator
from .entity import SpotifyEntity


@dataclass(frozen=True, kw_only=True)
class SpotifyAudioFeaturesSensorEntityDescription(SensorEntityDescription):
    """Describes Spotify sensor entity."""

    value_fn: Callable[[AudioFeatures], float]


AUDIO_FEATURE_SENSORS: tuple[SpotifyAudioFeaturesSensorEntityDescription, ...] = (
    SpotifyAudioFeaturesSensorEntityDescription(
        key="bpm",
        translation_key="song_tempo",
        native_unit_of_measurement="bpm",
        suggested_display_precision=0,
        value_fn=lambda audio_features: audio_features.tempo,
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
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if (audio_features := self.coordinator.data.audio_features) is None:
            return None
        return self.entity_description.value_fn(audio_features)
