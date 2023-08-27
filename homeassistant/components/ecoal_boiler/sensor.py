"""Allows reading temperatures from ecoal/esterownik.pl controller."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import AVAILABLE_SENSORS, DATA_ECOAL_BOILER, PERCENTAGE_SENSORS, TEMP_SENSORS


def getSensorClass(sensor_id):
    if sensor_id in TEMP_SENSORS:
        return EcoalTempSensor
    elif sensor_id in PERCENTAGE_SENSORS:
        return EcoalFuelPercentageSensor
    else:
        return None


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ecoal sensors."""
    if discovery_info is None:
        return
    devices = []
    ecoal_contr = hass.data[DATA_ECOAL_BOILER]
    for sensor_id in discovery_info:
        name = AVAILABLE_SENSORS[sensor_id]
        devices.append(getSensorClass(sensor_id)(ecoal_contr, name, sensor_id))
    add_entities(devices, True)


class EcoalTempSensor(SensorEntity):
    """Representation of a temperature sensor using ecoal status data."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, ecoal_contr, name, status_attr):
        """Initialize the sensor."""
        self._ecoal_contr = ecoal_contr
        self._attr_name = name
        self._status_attr = status_attr

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        # Old values read 0.5 back can still be used
        status = self._ecoal_contr.get_cached_status()
        self._attr_native_value = getattr(status, self._status_attr)


class EcoalFuelPercentageSensor(SensorEntity):
    """Representation of a fuel level in percent."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, ecoal_contr, name, status_attr):
        """Initialize the sensor."""
        self._ecoal_contr = ecoal_contr
        self._attr_name = name
        self._status_attr = status_attr

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        # Old values read 0.5 back can still be used
        status = self._ecoal_contr.get_cached_status()
        self._attr_native_value = 100 - (
            min(
                round(
                    status.feeder_current_run_time
                    / 60
                    / status.feeder_max_run_time
                    * 100,
                    1,
                ),
                100,
            )
        )
