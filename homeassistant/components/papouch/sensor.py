"""Sensor platform for the Papouch integration."""

from typing import Any, cast, override

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PapouchConfigEntry
from .coordinator import PapouchDataUpdateCoordinator
from .entity import PapouchEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PapouchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data
    device = coordinator.device

    entities = [
        PapouchSensor(coordinator, entry, sensor_data)
        for sensor_data in device.get_supported_sensors()
    ]

    async_add_entities(entities)


class PapouchSensor(PapouchEntity, SensorEntity):
    """Representation of a generic Papouch sensor."""

    def __init__(
        self,
        coordinator: PapouchDataUpdateCoordinator,
        entry: PapouchConfigEntry,
        sensor_data: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)

        mac = format_mac(coordinator.device.mac_address)

        self.item_id = sensor_data["item_id"]
        self.data_key = sensor_data["type"]
        self._attr_unique_id = f"{mac}_{self.data_key}_{self.item_id}"

        if sensor_data.get("use_custom_name", False):
            self._attr_name = sensor_data["name"]
        else:
            self._attr_translation_key = sensor_data["translation"]
            if "placeholder" in sensor_data:
                self._attr_translation_placeholders = sensor_data["placeholder"]

        if "device_class" in sensor_data:
            self._attr_device_class = sensor_data["device_class"]
        if "state_class" in sensor_data:
            self._attr_state_class = sensor_data["state_class"]
        if "unit" in sensor_data:
            self._attr_native_unit_of_measurement = sensor_data["unit"]

    @override
    @property
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self.data_key, {}).get(self.item_id)
        return cast(float | int | None, value)

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        for sensor_data in self.coordinator.device.get_supported_sensors():
            if (
                sensor_data.get("item_id") == self.item_id
                and sensor_data.get("type") == self.data_key
            ):
                if "unit" in sensor_data:
                    self._attr_native_unit_of_measurement = sensor_data["unit"]
                break

        super()._handle_coordinator_update()
