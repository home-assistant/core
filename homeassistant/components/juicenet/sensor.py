"""Support for monitoring juicenet/juicepoint/juicebox based EVSE sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    POWER_WATT,
    TEMP_CELSIUS,
    TIME_SECONDS,
)

from .const import DOMAIN, JUICENET_API, JUICENET_COORDINATOR
from .entity import JuiceNetDevice

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="status",
        name="Charging Status",
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage",
        name="Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
    ),
    SensorEntityDescription(
        key="amps",
        name="Amps",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="watts",
        name="Watts",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="charge_time",
        name="Charge time",
        native_unit_of_measurement=TIME_SECONDS,
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="energy_added",
        name="Energy added",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the JuiceNet Sensors."""
    juicenet_data = hass.data[DOMAIN][config_entry.entry_id]
    api = juicenet_data[JUICENET_API]
    coordinator = juicenet_data[JUICENET_COORDINATOR]

    entities = [
        JuiceNetSensorDevice(device, coordinator, description)
        for device in api.devices
        for description in SENSOR_TYPES
    ]
    async_add_entities(entities)


class JuiceNetSensorDevice(JuiceNetDevice, SensorEntity):
    """Implementation of a JuiceNet sensor."""

    def __init__(self, device, coordinator, description: SensorEntityDescription):
        """Initialise the sensor."""
        super().__init__(device, description.key, coordinator)
        self.entity_description = description
        self._attr_name = f"{self.device.name} {description.name}"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        icon = None
        if self.entity_description.key == "status":
            status = self.device.status
            if status == "standby":
                icon = "mdi:power-plug-off"
            elif status == "plugged":
                icon = "mdi:power-plug"
            elif status == "charging":
                icon = "mdi:battery-positive"
        else:
            icon = self.entity_description.icon
        return icon

    @property
    def native_value(self):
        """Return the state."""
        return getattr(self.device, self.entity_description.key, None)
