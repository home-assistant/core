"""Time platform for Enphase Envoy solar energy monitor."""

from datetime import time
from typing import override

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EnphaseConfigEntry, EnphaseUpdateCoordinator
from .entity import EnvoyGeneratorScheduleEntity, exception_handler

PARALLEL_UPDATES = 1

GENERATOR_EXERCISE_START_ENTITY = TimeEntityDescription(
    key="generator_exercise_start_time",
    translation_key="generator_exercise_start_time",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnphaseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Enphase Envoy time platform."""
    coordinator = config_entry.runtime_data
    envoy_data = coordinator.envoy.data
    assert envoy_data is not None
    entities: list[TimeEntity] = []
    if envoy_data.generator_schedule:
        entities.append(
            EnvoyGeneratorExerciseStartTimeEntity(
                coordinator, GENERATOR_EXERCISE_START_ENTITY
            )
        )
    async_add_entities(entities)


class EnvoyGeneratorExerciseStartTimeEntity(EnvoyGeneratorScheduleEntity, TimeEntity):
    """Representation of the standby generator exercise start time entity."""

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: TimeEntityDescription,
    ) -> None:
        """Initialize the generator exercise start time entity."""
        super().__init__(coordinator, description)
        self.envoy = coordinator.envoy

    @property
    @override
    def native_value(self) -> time | None:
        """Return the time of day the generator exercise starts."""
        if (schedule := self.data.generator_schedule) is None:
            return None
        return time(schedule.exercise_start // 60, schedule.exercise_start % 60)

    @exception_handler
    @override
    async def async_set_value(self, value: time) -> None:
        """Update the exercise start time, keeping the rest of the schedule."""
        await self.envoy.update_generator_schedule(
            {"exercise_start": value.hour * 60 + value.minute}, refresh=True
        )
        await self.coordinator.async_request_refresh()
