"""Sensor platform for Spotify."""

from collections.abc import Callable
from dataclasses import dataclass

from spotifyaio.models import AudioFeatures

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, SpotifyConfigEntry
from .coordinator import SpotifyCoordinator


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

    user_id = entry.unique_id

    assert user_id is not None

    async_add_entities(
        SpotifyAudioFeatureSensor(coordinator, description, user_id, entry.title)
        for description in AUDIO_FEATURE_SENSORS
    )


class SpotifyAudioFeatureSensor(CoordinatorEntity[SpotifyCoordinator], SensorEntity):
    """Representation of a Spotify sensor."""

    _attr_has_entity_name = True
    entity_description: SpotifyAudioFeaturesSensorEntityDescription

    def __init__(
        self,
        coordinator: SpotifyCoordinator,
        entity_description: SpotifyAudioFeaturesSensorEntityDescription,
        user_id: str,
        name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{user_id}_{entity_description.key}"
        self.entity_description = entity_description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
            manufacturer="Spotify AB",
            model=f"Spotify {coordinator.current_user.product}",
            name=f"Spotify {name}",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://open.spotify.com",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if (audio_features := self.coordinator.data.audio_features) is None:
            return None
        return self.entity_description.value_fn(audio_features)
