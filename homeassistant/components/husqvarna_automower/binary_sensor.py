"""Creates the binary sensor entities for the mower."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from aioautomower.model import MowerActivities, MowerAttributes

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AutomowerConfigEntry
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity

_LOGGER = logging.getLogger(__name__)
# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AutomowerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Automower binary sensor entity."""

    value_fn: Callable[[MowerAttributes], bool]


MOWER_BINARY_SENSOR_TYPES: tuple[AutomowerBinarySensorEntityDescription, ...] = (
    AutomowerBinarySensorEntityDescription(
        key="battery_charging",
        value_fn=lambda data: data.mower.activity == MowerActivities.CHARGING,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    AutomowerBinarySensorEntityDescription(
        key="leaving_dock",
        translation_key="leaving_dock",
        value_fn=lambda data: data.mower.activity == MowerActivities.LEAVING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensor platform."""
    coordinator = entry.runtime_data

    def _async_add_new_devices(mower_ids: set[str]) -> None:
        async_add_entities(
            AutomowerBinarySensorEntity(mower_id, coordinator, description)
            for mower_id in mower_ids
            for description in MOWER_BINARY_SENSOR_TYPES
        )

    coordinator.new_devices_callbacks.append(_async_add_new_devices)
    _async_add_new_devices(set(coordinator.data))


class AutomowerBinarySensorEntity(AutomowerBaseEntity, BinarySensorEntity):
    """Defining the Automower Sensors with AutomowerBinarySensorEntityDescription."""

    entity_description: AutomowerBinarySensorEntityDescription

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        description: AutomowerBinarySensorEntityDescription,
    ) -> None:
        """Set up AutomowerSensors."""
        super().__init__(mower_id, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.mower_attributes)
