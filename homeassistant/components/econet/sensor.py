"""Support for Rheem EcoNet water heaters."""
from pyeconet.equipment import EquipmentType

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_SIGNAL_STRENGTH,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    VOLUME_GALLONS,
)

from . import EcoNetEntity
from .const import DOMAIN, EQUIPMENT

ENERGY_KILO_BRITISH_THERMAL_UNIT = "kBtu"

TANK_HEALTH = "tank_health"
AVAILIBLE_HOT_WATER = "availible_hot_water"
COMPRESSOR_HEALTH = "compressor_health"
OVERRIDE_STATUS = "oveerride_status"
WATER_USAGE_TODAY = "water_usage_today"
POWER_USAGE_TODAY = "power_usage_today"
ALERT_COUNT = "alert_count"
WIFI_SIGNAL = "wifi_signal"
RUNNING_STATE = "running_state"

SENSOR_NAMES_TO_ATTRIBUTES = {
    TANK_HEALTH: "tank_health",
    AVAILIBLE_HOT_WATER: "tank_hot_water_availability",
    COMPRESSOR_HEALTH: "compressor_health",
    OVERRIDE_STATUS: "override_status",
    WATER_USAGE_TODAY: "todays_water_usage",
    POWER_USAGE_TODAY: "todays_energy_usage",
    ALERT_COUNT: "alert_count",
    WIFI_SIGNAL: "wifi_signal",
    RUNNING_STATE: "running_state",
}

SENSOR_NAMES_TO_UNIT_OF_MEASUREMENT = {
    TANK_HEALTH: PERCENTAGE,
    AVAILIBLE_HOT_WATER: PERCENTAGE,
    COMPRESSOR_HEALTH: PERCENTAGE,
    OVERRIDE_STATUS: None,
    WATER_USAGE_TODAY: VOLUME_GALLONS,
    POWER_USAGE_TODAY: None,  # Depends on unit type
    ALERT_COUNT: None,
    WIFI_SIGNAL: DEVICE_CLASS_SIGNAL_STRENGTH,
    RUNNING_STATE: None,  # This is just a string
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up EcoNet sensor based on a config entry."""

    equipment = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    sensors = []
    all_equipment = equipment[EquipmentType.WATER_HEATER].copy()
    all_equipment.extend(equipment[EquipmentType.THERMOSTAT].copy())

    for _equip in all_equipment:
        for name, attribute in SENSOR_NAMES_TO_ATTRIBUTES.items():
            if getattr(_equip, attribute, None) is not None:
                sensors.append(EcoNetSensor(_equip, name))
        # This is None to start with and all device have it
        sensors.append(EcoNetSensor(_equip, WIFI_SIGNAL))

    for water_heater in equipment[EquipmentType.WATER_HEATER]:
        # These aren't part of the device and start off as None in pyeconet so always add them
        sensors.append(EcoNetSensor(water_heater, WATER_USAGE_TODAY))
        sensors.append(EcoNetSensor(water_heater, POWER_USAGE_TODAY))

    async_add_entities(sensors)


class EcoNetSensor(EcoNetEntity, SensorEntity):
    """Define a Econet sensor."""

    def __init__(self, econet_device, device_name):
        """Initialize."""
        super().__init__(econet_device)
        self._econet = econet_device
        self._device_name = device_name

    @property
    def native_value(self):
        """Return sensors state."""
        value = getattr(self._econet, SENSOR_NAMES_TO_ATTRIBUTES[self._device_name])
        if isinstance(value, float):
            value = round(value, 2)
        return value

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        unit_of_measurement = SENSOR_NAMES_TO_UNIT_OF_MEASUREMENT[self._device_name]
        if self._device_name == POWER_USAGE_TODAY:
            if self._econet.energy_type == ENERGY_KILO_BRITISH_THERMAL_UNIT.upper():
                unit_of_measurement = ENERGY_KILO_BRITISH_THERMAL_UNIT
            else:
                unit_of_measurement = ENERGY_KILO_WATT_HOUR
        return unit_of_measurement

    @property
    def name(self):
        """Return the name of the entity."""
        return f"{self._econet.device_name}_{self._device_name}"

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return (
            f"{self._econet.device_id}_{self._econet.device_name}_{self._device_name}"
        )
