"""Number platform for the Bosch Smart Camera integration."""

import math
from typing import override

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import BoschCameraConfigEntry, BoschCameraCoordinator
from .entity import BoschCameraEntity

# Serialize the cloud writes.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoschCameraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the speaker level of the cameras that have a speaker."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new_cameras() -> None:
        # Forget removed cameras so one that comes back gets a new entity.
        known.intersection_update(coordinator.data)
        new = {
            camera_id
            for camera_id in coordinator.data
            if camera_id not in known
            and (settings := coordinator.audio_settings.get(camera_id)) is not None
            and settings.speaker_level is not None
        }
        known.update(new)
        async_add_entities(
            BoschSpeakerLevelNumber(coordinator, camera_id) for camera_id in new
        )

    entry.async_on_unload(coordinator.async_add_listener(_add_new_cameras))
    _add_new_cameras()


class BoschSpeakerLevelNumber(BoschCameraEntity, NumberEntity):
    """Speaker level of a camera."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "speaker_level"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: BoschCameraCoordinator, camera_id: str) -> None:
        """Initialize the number."""
        super().__init__(coordinator, camera_id)
        self._attr_unique_id = f"{camera_id}_speaker_level"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the speaker level."""
        settings = self.coordinator.audio_settings.get(self._camera_id)
        return None if settings is None else settings.speaker_level

    @property
    @override
    def available(self) -> bool:
        """Return whether the camera reports a speaker level."""
        return (
            super().available
            and self._camera_id in self.coordinator.data
            and self.native_value is not None
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the speaker level."""
        if not math.isfinite(value):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_speaker_level"
            )
        await self.coordinator.async_set_speaker_level(self._camera_id, round(value))
