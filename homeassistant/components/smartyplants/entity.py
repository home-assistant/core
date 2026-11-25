"""Shared base entity — this is where each sensor becomes an HA device."""

from collections.abc import Callable, Iterable
from typing import override

from pysmartyplants import Sensor

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import SmartyPlantsConfigEntry, SmartyPlantsCoordinator


class SmartyPlantsEntity(CoordinatorEntity[SmartyPlantsCoordinator]):
    """Common device wiring for every SmartyPlants entity."""

    _attr_has_entity_name = True
    # Cleared by the entities that report on the sensor itself, which have to
    # keep answering once it goes offline.
    _requires_online = True

    def __init__(self, coordinator: SmartyPlantsCoordinator, sensor_id: str) -> None:
        """Bind this entity to one physical sensor."""
        super().__init__(coordinator)
        self._sensor_id = sensor_id

        sensor = self.sensor
        plant = sensor.plant

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=(plant.name if plant else None) or sensor.name or sensor.identifier,
            serial_number=sensor.identifier,
        )

    @property
    def sensor(self) -> Sensor:
        """Return this sensor's slice of the last update."""
        return self.coordinator.data[self._sensor_id]

    @property
    @override
    def available(self) -> bool:
        """Report unavailable once the sensor stops reporting."""
        if not super().available or self._sensor_id not in self.coordinator.data:
            return False
        return self.sensor.is_online or not self._requires_online


@callback
def async_add_entities_for_sensors(
    entry: SmartyPlantsConfigEntry,
    coordinator: SmartyPlantsCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    build: Callable[[str], Iterable[SmartyPlantsEntity]],
) -> None:
    """Add entities for sensors as they appear, including after setup.

    A sensor paired in the SmartyPlants app shows up in a later poll, so the
    platforms follow the coordinator rather than only its first refresh.
    """
    known: set[str] = set()

    @callback
    def _async_add_new() -> None:
        current = set(coordinator.data)
        # Forget ids that have gone, otherwise a sensor that is removed and
        # later paired again would never get its entities back.
        known.intersection_update(current)

        if not (new_ids := current - known):
            return
        known.update(new_ids)
        async_add_entities(
            entity for sensor_id in sorted(new_ids) for entity in build(sensor_id)
        )

    _async_add_new()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))
