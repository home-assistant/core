"""Platform for PAJ GPS sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass

from pajgps_api.models.trackpoint import TrackPoint

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PajGpsConfigEntry
from .coordinator import PajGpsCoordinator
from .entity import PajGpsEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PajGpsSensorEntityDescription(SensorEntityDescription):
    """Describes a PAJ GPS sensor entity."""

    value_fn: Callable[[TrackPoint], int | None]


SENSOR_DESCRIPTIONS: tuple[PajGpsSensorEntityDescription, ...] = (
    PajGpsSensorEntityDescription(
        key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda tp: tp.speed,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PajGpsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PAJ GPS sensor entities from a config entry."""
    coordinator = config_entry.runtime_data

    known_device_ids: set[int] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add entities for any device IDs not yet tracked."""
        current_ids = set(coordinator.data.devices.keys())
        new_ids = current_ids - known_device_ids
        if new_ids:
            sorted_new_ids = sorted(new_ids)
            async_add_entities(
                PajGpsSensor(coordinator, device_id, description)
                for device_id in sorted_new_ids
                for description in SENSOR_DESCRIPTIONS
            )
            known_device_ids.update(sorted_new_ids)

    _async_add_new_devices()

    config_entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class PajGpsSensor(PajGpsEntity, SensorEntity):
    """Sensor entity that reads data from the coordinator snapshot."""

    entity_description: PajGpsSensorEntityDescription

    def __init__(
        self,
        coordinator: PajGpsCoordinator,
        device_id: int,
        description: PajGpsSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.user_id}_{device_id}_{description.key}"

    @property
    def native_value(self) -> int | None:
        """Return the sensor value from the latest trackpoint."""
        tp = self.coordinator.data.positions.get(self._device_id)
        if tp is None:
            return None
        return self.entity_description.value_fn(tp)
