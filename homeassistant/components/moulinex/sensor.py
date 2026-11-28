"""Sensor platform for the Moulinex integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiomoulinex import Appliance, CookingState, CookingStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import MoulinexConfigEntry, MoulinexDataUpdateCoordinator
from .entity import MoulinexEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MoulinexSensorEntityDescription(SensorEntityDescription):
    """Describes a Moulinex sensor entity."""

    value_fn: Callable[[Appliance, CookingStatus], StateType]
    options_fn: Callable[[Appliance], list[str]] | None = None


SENSORS: tuple[MoulinexSensorEntityDescription, ...] = (
    MoulinexSensorEntityDescription(
        key="state",
        translation_key="state",
        name=None,
        device_class=SensorDeviceClass.ENUM,
        options=[state.value for state in CookingState],
        value_fn=lambda _, status: status.state,
    ),
    MoulinexSensorEntityDescription(
        key="program",
        translation_key="program",
        device_class=SensorDeviceClass.ENUM,
        options_fn=lambda appliance: list(appliance.programs),
        value_fn=lambda appliance, status: appliance.program(status),
    ),
    MoulinexSensorEntityDescription(
        key="progress",
        translation_key="progress",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda _, status: status.phase_progress,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MoulinexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Moulinex sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        MoulinexSensor(coordinator, appliance, description)
        for appliance in coordinator.client.appliances.values()
        for description in SENSORS
    )


class MoulinexSensor(MoulinexEntity, SensorEntity):
    """Representation of a Moulinex sensor."""

    entity_description: MoulinexSensorEntityDescription

    def __init__(
        self,
        coordinator: MoulinexDataUpdateCoordinator,
        appliance: Appliance,
        description: MoulinexSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, appliance, description.key)
        self.entity_description = description
        if description.options_fn is not None:
            self._attr_options = description.options_fn(appliance)

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        if (status := self.appliance_state.status) is None:
            return None
        return self.entity_description.value_fn(self.appliance, status)
