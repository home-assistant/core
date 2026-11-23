"""Binary sensor platform for the Helty Flow Cloud integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pyheltycloud import Alarm, HeltyState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HeltyCloudConfigEntry, HeltyCloudDataUpdateCoordinator
from .entity import HeltyCloudEntity

PARALLEL_UPDATES = 0


def _alarm(alarm: Alarm) -> Callable[[HeltyState], bool | None]:
    """Read one alarm, or None when the state carries no alarm bitmap."""

    def is_on(state: HeltyState) -> bool | None:
        if (flags := state.alarm_flags) is None:
            return None
        return bool(flags & alarm)

    return is_on


@dataclass(frozen=True, kw_only=True)
class HeltyCloudBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Helty Flow Cloud binary sensor."""

    is_on_fn: Callable[[HeltyState], bool | None]


BINARY_SENSORS: tuple[HeltyCloudBinarySensorEntityDescription, ...] = (
    HeltyCloudBinarySensorEntityDescription(
        key="filter",
        translation_key="filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_alarm(Alarm.FILTER),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeltyCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors of every VMC on the account."""
    async_add_entities(
        HeltyCloudBinarySensor(coordinator, description)
        for coordinator in entry.runtime_data
        for description in BINARY_SENSORS
    )


class HeltyCloudBinarySensor(HeltyCloudEntity, BinarySensorEntity):
    """An alarm raised by the ventilation unit."""

    entity_description: HeltyCloudBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: HeltyCloudDataUpdateCoordinator,
        description: HeltyCloudBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device.serial_number}_{description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the alarm is raised."""
        return self.entity_description.is_on_fn(self.coordinator.data)
