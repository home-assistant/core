"""Support for mill wifi-enabled home heaters."""
from __future__ import annotations

import mill

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_USERNAME,
    ENERGY_KILO_WATT_HOUR,
    ENTITY_CATEGORY_DIAGNOSTIC,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BATTERY,
    CLOUD,
    CONNECTION_TYPE,
    CONSUMPTION_TODAY,
    CONSUMPTION_YEAR,
    DOMAIN,
    ECO2,
    HUMIDITY,
    LOCAL,
    MANUFACTURER,
    TEMPERATURE,
    TVOC,
)

HEATER_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=CONSUMPTION_YEAR,
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        name="Year consumption",
    ),
    SensorEntityDescription(
        key=CONSUMPTION_TODAY,
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        name="Day consumption",
    ),
)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=TEMPERATURE,
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        name="Temperature",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=HUMIDITY,
        device_class=DEVICE_CLASS_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        name="Humidity",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=BATTERY,
        device_class=DEVICE_CLASS_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        name="Battery",
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=ECO2,
        device_class=DEVICE_CLASS_CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        name="Estimated CO2",
    ),
    SensorEntityDescription(
        key=TVOC,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        name="TVOC",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Mill sensor."""
    if entry.data.get(CONNECTION_TYPE) == LOCAL:
        return

    mill_data_coordinator = hass.data[DOMAIN][CLOUD][entry.data[CONF_USERNAME]]

    entities = [
        MillSensor(
            mill_data_coordinator,
            entity_description,
            mill_device,
        )
        for mill_device in mill_data_coordinator.data.values()
        for entity_description in (
            HEATER_SENSOR_TYPES
            if isinstance(mill_device, mill.Heater)
            else SENSOR_TYPES
        )
    ]

    async_add_entities(entities)


class MillSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Mill Sensor device."""

    def __init__(self, coordinator, entity_description, mill_device):
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._id = mill_device.device_id
        self.entity_description = entity_description
        self._available = False

        self._attr_name = f"{mill_device.name} {entity_description.name}"
        self._attr_unique_id = f"{mill_device.device_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mill_device.device_id)},
            name=self.name,
            manufacturer=MANUFACTURER,
        )
        if isinstance(mill_device, mill.Heater):
            self._attr_device_info["model"] = f"Generation {mill_device.generation}"
        elif isinstance(mill_device, mill.Sensor):
            self._attr_device_info["model"] = "Mill Sense Air"
        self._update_attr(mill_device)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr(self.coordinator.data[self._id])
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._available

    @callback
    def _update_attr(self, device):
        self._available = device.available
        self._attr_native_value = getattr(device, self.entity_description.key)
