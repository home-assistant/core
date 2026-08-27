"""Shared base entity — this is where each sensor becomes an HA device."""

from collections.abc import Callable, Iterable
from typing import Any, override

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, PLANT_ONLY_MODEL
from .coordinator import SmartyPlantsConfigEntry, SmartyPlantsCoordinator, is_usable


class SmartyPlantsEntity(CoordinatorEntity[SmartyPlantsCoordinator]):
    """Common device wiring for every SmartyPlants entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SmartyPlantsCoordinator, sensor_id: str) -> None:
        """Bind this entity to one physical sensor."""
        super().__init__(coordinator)
        self._sensor_id = sensor_id

        sensor = self.sensor
        plant = sensor.get("plant") or {}

        # Registering a device is what puts these entities on the auto-generated
        # dashboard and lets the user assign them to an area.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor_id)},
            manufacturer=MANUFACTURER,
            # A plant with no sensor still gets a device so the user can see it
            # and knows to attach one.
            model=PLANT_ONLY_MODEL if sensor.get("isPlantOnly") else MODEL,
            name=plant.get("name") or sensor.get("name") or sensor.get("identifier"),
            serial_number=sensor.get("identifier"),
        )

    @property
    def sensor(self) -> dict[str, Any]:
        """Return this sensor's slice of the last update."""
        return self.coordinator.data.get(self._sensor_id, {})

    @property
    def readings(self) -> dict[str, Any]:
        """Return the readings block, or an empty dict when there is none."""
        return self.sensor.get("readings") or {}

    @property
    @override
    def available(self) -> bool:
        """Mark entities unavailable once the sensor drops out of the payload."""
        return self._is_present

    @property
    def _is_present(self) -> bool:
        """Return True while this sensor is still in the coordinator payload."""
        return (
            CoordinatorEntity.available.fget(self)  # type: ignore[attr-defined]
            and self._sensor_id in self.coordinator.data
        )

    def _availability_for(
        self, *, stale_sensitive: bool, requires_sensor: bool
    ) -> bool:
        """Apply the shared availability rule for a described entity.

        Live measurements go away when the data cannot be trusted; sensor
        diagnostics stay visible unless there is no sensor at all.
        """
        if not self._is_present:
            return False
        if stale_sensitive:
            return self.data_is_fresh
        return not (requires_sensor and self.sensor.get("isPlantOnly"))

    @property
    def data_is_fresh(self) -> bool:
        """Return True when this sensor is online and its reading is recent."""
        return is_usable(self.sensor)


@callback
def async_setup_dynamic_entities(
    entry: SmartyPlantsConfigEntry,
    coordinator: SmartyPlantsCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    build: Callable[[str], Iterable[SmartyPlantsEntity]],
) -> None:
    """Add entities for sensors as they appear, including after setup.

    Sensors added in the SmartyPlants app show up in a later poll, so the
    platforms subscribe to the coordinator rather than only reading the first
    refresh. Removal is handled centrally in the coordinator, which drops the
    device and lets Home Assistant clean up its entities.
    """
    known: set[str] = set()

    @callback
    def _async_add_new() -> None:
        current = set(coordinator.data)
        # Forget ids that have gone, otherwise a sensor that is removed and
        # later re-paired would never get its entities back.
        known.intersection_update(current)

        if not (new_ids := current - known):
            return
        known.update(new_ids)
        async_add_entities(
            entity for sensor_id in new_ids for entity in build(sensor_id)
        )

    _async_add_new()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))
