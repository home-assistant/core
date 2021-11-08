"""Support for mill wifi-enabled home heaters."""
from __future__ import annotations

from homeassistant.components.sensor import (
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, POWER_WATT, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="control_signal",
        native_unit_of_measurement=PERCENTAGE,
        name="Control signal",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_power",
        device_class=DEVICE_CLASS_POWER,
        native_unit_of_measurement=POWER_WATT,
        name="Current power",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="raw_ambient_temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        name="Uncalibrated temperature",
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Mill sensor."""

    entities = [
        MillSensor(
            device_id,
            mill_data_coordinator,
            entity_description,
        )
        for device_id, mill_data_coordinator in hass.data[DOMAIN].items()
        for entity_description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class MillSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Mill Sensor device."""

    def __init__(self, device_id, coordinator, entity_description):
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_name = (
            f"{coordinator.mill_data_connection.name} {entity_description.name}"
        )
        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.mill_data_connection.url,
            identifiers={(DOMAIN, device_id)},
            manufacturer=MANUFACTURER,
            name=coordinator.mill_data_connection.name,
            sw_version=coordinator.mill_data_connection.version,
        )
        print(self.device_info)

        self._update_attr()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr()
        self.async_write_ha_state()

    @callback
    def _update_attr(self) -> None:
        self._attr_native_value = self.coordinator.data[self.entity_description.key]
