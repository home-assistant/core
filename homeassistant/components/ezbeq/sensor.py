"""Sensor platform for the ezbeq Profile Loader integration."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import EzBEQConfigEntry
from .const import CURRENT_PROFILE, DEVICES
from .coordinator import EzBEQCoordinator
from .entity import EzBEQEntity


@dataclass(frozen=True, kw_only=True)
class EzBEQSensorEntityDescription(SensorEntityDescription):
    """Describe EzBEQ sensor entity."""

    value_fn: Callable[[EzBEQCoordinator], StateType]


SENSORS: tuple[EzBEQSensorEntityDescription, ...] = (
    EzBEQSensorEntityDescription(
        key=CURRENT_PROFILE,
        value_fn=lambda coordinator: coordinator.data.get(CURRENT_PROFILE)
        if coordinator.data.get(CURRENT_PROFILE) != ""
        else None,
        translation_key=CURRENT_PROFILE,
    ),
    EzBEQSensorEntityDescription(
        key=DEVICES,
        # make a list of device names
        value_fn=lambda coordinator: ", ".join(
            f"{device.name}" for device in coordinator.devices
        ),
        translation_key=DEVICES,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzBEQConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(EzBEQSensor(coordinator, description) for description in SENSORS)


class EzBEQSensor(EzBEQEntity, SensorEntity):
    """Base class for EzBEQ sensors."""

    def __init__(
        self,
        coordinator: EzBEQCoordinator,
        description: EzBEQSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description: EzBEQSensorEntityDescription = description
        self._attr_unique_id = f"{coordinator.client.server_url}_{description.key}"

    @property
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator)
