"""Sensor platform for Spotify."""

from dataclasses import dataclass
from typing import Callable

from spotifyaio.models import AudioFeatures

from . import DOMAIN, SpotifyConfigEntry
from .coordinator import SpotifyCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.core import HomeAssistant
from ...helpers.entity_platform import AddEntitiesCallback


@dataclass(frozen=True, kw_only=True)
class SpotifyAudioFeaturesSensorEntityDescription(SensorEntityDescription):
    """Describes Spotify sensor entity."""

    value_fn: Callable[[AudioFeatures], StateType]


AUDIO_FEATURE_SENSORS: tuple[SpotifyAudioFeaturesSensorEntityDescription, ...] = (
)


async def async_setup_entry(hass: HomeAssistant, entry: SpotifyConfigEntry, async_add_entities: AddEntitiesCallback) -> None:


class SpotifyAudioFeatureSensor(CoordinatorEntity[SpotifyCoordinator], SensorEntity):
    """Representation of a Spotify sensor."""

    _attr_has_entity_name = True
    entity_description: SpotifyAudioFeaturesSensorEntityDescription

    def __init__(
        self,
        coordinator: SpotifyCoordinator,
        entity_description: SpotifyAudioFeaturesSensorEntityDescription,
        user_id: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{user_id}_{entity_description.key}"
        self.entity_description = entity_description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if (audio_features := self.coordinator.data.audio_features) is None:
            return None
        return self.entity_description.value_fn(audio_features)