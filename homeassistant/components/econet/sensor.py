"""Support for Rheem EcoNet water heaters."""
from pyeconet.equipment import EquipmentType

from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
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


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up EcoNet sensor based on a config entry."""
    equipment = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    sensors = []
    for water_heater in equipment[EquipmentType.WATER_HEATER]:
        if water_heater.tank_hot_water_availability is not None:
            sensors.append(EcoNetSensor(water_heater, AVAILIBLE_HOT_WATER))
        if water_heater.tank_health is not None:
            sensors.append(EcoNetSensor(water_heater, TANK_HEALTH))
        if water_heater.compressor_health is not None:
            sensors.append(EcoNetSensor(water_heater, COMPRESSOR_HEALTH))
        if water_heater.override_status:
            sensors.append(EcoNetSensor(water_heater, OVERRIDE_STATUS))
        if water_heater.running_state is not None:
            sensors.append(EcoNetSensor(water_heater, RUNNING_STATE))
        # All units have this
        sensors.append(EcoNetSensor(water_heater, ALERT_COUNT))
        # These aren't part of the device and start off as None in pyeconet so always add them
        sensors.append(EcoNetSensor(water_heater, WATER_USAGE_TODAY))
        sensors.append(EcoNetSensor(water_heater, POWER_USAGE_TODAY))
        sensors.append(EcoNetSensor(water_heater, WIFI_SIGNAL))
    async_add_entities(sensors)


class EcoNetSensor(EcoNetEntity):
    """Define a Econet sensor."""

    def __init__(self, econet_device, device_name):
        """Initialize."""
        super().__init__(econet_device)
        self._econet = econet_device
        self._device_name = device_name

    @property
    def state(self):
        """Return sensors state."""
        if self._device_name == AVAILIBLE_HOT_WATER:
            return self._econet.tank_hot_water_availability
        if self._device_name == TANK_HEALTH:
            return self._econet.tank_health
        if self._device_name == COMPRESSOR_HEALTH:
            return self._econet.compressor_health
        if self._device_name == OVERRIDE_STATUS:
            return self._econet.oveerride_status
        if self._device_name == WATER_USAGE_TODAY:
            if self._econet.todays_water_usage:
                return round(self._econet.todays_water_usage, 2)
            return None
        if self._device_name == POWER_USAGE_TODAY:
            if self._econet.todays_energy_usage:
                return round(self._econet.todays_energy_usage, 2)
            return None
        if self._device_name == WIFI_SIGNAL:
            if self._econet.wifi_signal:
                return self._econet.wifi_signal
            return None
        if self._device_name == ALERT_COUNT:
            return self._econet.alert_count
        if self._device_name == RUNNING_STATE:
            return self._econet.running_state
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self._device_name == AVAILIBLE_HOT_WATER:
            return PERCENTAGE
        if self._device_name == TANK_HEALTH:
            return PERCENTAGE
        if self._device_name == COMPRESSOR_HEALTH:
            return PERCENTAGE
        if self._device_name == WATER_USAGE_TODAY:
            return VOLUME_GALLONS
        if self._device_name == POWER_USAGE_TODAY:
            if self._econet.energy_type == ENERGY_KILO_BRITISH_THERMAL_UNIT.upper():
                return ENERGY_KILO_BRITISH_THERMAL_UNIT
            return ENERGY_KILO_WATT_HOUR
        if self._device_name == WIFI_SIGNAL:
            return SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        return None

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
