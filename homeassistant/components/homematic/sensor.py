"""Support for HomeMatic sensors."""

from __future__ import annotations

from copy import copy
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_NAME,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_DISCOVER_DEVICES, ATTR_PARAM
from .entity import HMDevice

_LOGGER = logging.getLogger(__name__)

HM_STATE_HA_CAST = {
    "IPGarage": {0: "closed", 1: "open", 2: "ventilation", 3: None},
    "RotaryHandleSensor": {0: "closed", 1: "tilted", 2: "open"},
    "RotaryHandleSensorIP": {0: "closed", 1: "tilted", 2: "open"},
    "WaterSensor": {0: "dry", 1: "wet", 2: "water"},
    "CO2Sensor": {0: "normal", 1: "added", 2: "strong"},
    "IPSmoke": {0: "off", 1: "primary", 2: "intrusion", 3: "secondary"},
    "RFSiren": {
        0: "disarmed",
        1: "extsens_armed",
        2: "allsens_armed",
        3: "alarm_blocked",
    },
    "IPLockDLD": {0: None, 1: "locked", 2: "unlocked"},
}


SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "HUMIDITY": SensorEntityDescription(
        key="HUMIDITY",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ACTUAL_TEMPERATURE": SensorEntityDescription(
        key="ACTUAL_TEMPERATURE",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "TEMPERATURE": SensorEntityDescription(
        key="TEMPERATURE",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "LUX": SensorEntityDescription(
        key="LUX",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CURRENT_ILLUMINATION": SensorEntityDescription(
        key="CURRENT_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ILLUMINATION": SensorEntityDescription(
        key="ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "AVERAGE_ILLUMINATION": SensorEntityDescription(
        key="AVERAGE_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "LOWEST_ILLUMINATION": SensorEntityDescription(
        key="LOWEST_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "HIGHEST_ILLUMINATION": SensorEntityDescription(
        key="HIGHEST_ILLUMINATION",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "POWER": SensorEntityDescription(
        key="POWER",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "IEC_POWER": SensorEntityDescription(
        key="IEC_POWER",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CURRENT": SensorEntityDescription(
        key="CURRENT",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CONCENTRATION": SensorEntityDescription(
        key="CONCENTRATION",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ENERGY_COUNTER": SensorEntityDescription(
        key="ENERGY_COUNTER",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "IEC_ENERGY_COUNTER": SensorEntityDescription(
        key="IEC_ENERGY_COUNTER",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "VOLTAGE": SensorEntityDescription(
        key="VOLTAGE",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "GAS_POWER": SensorEntityDescription(
        key="GAS_POWER",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
    ),
    "GAS_ENERGY_COUNTER": SensorEntityDescription(
        key="GAS_ENERGY_COUNTER",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "RAIN_COUNTER": SensorEntityDescription(
        key="RAIN_COUNTER",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    "WIND_SPEED": SensorEntityDescription(
        key="WIND_SPEED",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        icon="mdi:weather-windy",
    ),
    "WIND_DIRECTION": SensorEntityDescription(
        key="WIND_DIRECTION",
        native_unit_of_measurement=DEGREE,
    ),
    "WIND_DIRECTION_RANGE": SensorEntityDescription(
        key="WIND_DIRECTION_RANGE",
        native_unit_of_measurement=DEGREE,
    ),
    "SUNSHINEDURATION": SensorEntityDescription(
        key="SUNSHINEDURATION",
        native_unit_of_measurement="#",
    ),
    "AIR_PRESSURE": SensorEntityDescription(
        key="AIR_PRESSURE",
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "FREQUENCY": SensorEntityDescription(
        key="FREQUENCY",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
    ),
    "VALUE": SensorEntityDescription(
        key="VALUE",
        native_unit_of_measurement="#",
    ),
    "VALVE_STATE": SensorEntityDescription(
        key="VALVE_STATE",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "CARRIER_SENSE_LEVEL": SensorEntityDescription(
        key="CARRIER_SENSE_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "DUTY_CYCLE_LEVEL": SensorEntityDescription(
        key="DUTY_CYCLE_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "BRIGHTNESS": SensorEntityDescription(
        key="BRIGHTNESS",
        native_unit_of_measurement="#",
        icon="mdi:invert-colors",
    ),
    "MASS_CONCENTRATION_PM_1": SensorEntityDescription(
        key="MASS_CONCENTRATION_PM_1",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "MASS_CONCENTRATION_PM_2_5": SensorEntityDescription(
        key="MASS_CONCENTRATION_PM_2_5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "MASS_CONCENTRATION_PM_10": SensorEntityDescription(
        key="MASS_CONCENTRATION_PM_10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "MASS_CONCENTRATION_PM_1_24H_AVERAGE": SensorEntityDescription(
        key="MASS_CONCENTRATION_PM_1_24H_AVERAGE",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "MASS_CONCENTRATION_PM_2_5_24H_AVERAGE": SensorEntityDescription(
        key="MASS_CONCENTRATION_PM_2_5_24H_AVERAGE",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "MASS_CONCENTRATION_PM_10_24H_AVERAGE": SensorEntityDescription(
        key="MASS_CONCENTRATION_PM_10_24H_AVERAGE",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "STATE": SensorEntityDescription(
        key="STATE",
    ),
    "SMOKE_DETECTOR_ALARM_STATUS": SensorEntityDescription(
        key="SMOKE_DETECTOR_ALARM_STATUS",
    ),
    "WIND_DIR": SensorEntityDescription(
        key="WIND_DIR",
    ),
    "WIND_DIR_RANGE": SensorEntityDescription(
        key="WIND_DIR_RANGE",
    ),
    "CONCENTRATION_STATUS": SensorEntityDescription(
        key="CONCENTRATION_STATUS",
    ),
    "PASSAGE_COUNTER_VALUE": SensorEntityDescription(
        key="PASSAGE_COUNTER_VALUE",
    ),
    "LEVEL": SensorEntityDescription(
        key="LEVEL",
    ),
    "LEVEL_2": SensorEntityDescription(
        key="LEVEL_2",
    ),
    "DOOR_STATE": SensorEntityDescription(
        key="DOOR_STATE",
    ),
    "FILLING_LEVEL": SensorEntityDescription(
        key="FILLING_LEVEL",
    ),
}

DEFAULT_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="",
    entity_registry_enabled_default=True,
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the HomeMatic sensor platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        state = conf.get(ATTR_PARAM)
        if (entity_desc := SENSOR_DESCRIPTIONS.get(state)) is None:
            name = conf.get(ATTR_NAME)
            _LOGGER.warning(
                (
                    "Sensor (%s) entity description is missing. Sensor state (%s) needs"
                    " to be maintained"
                ),
                name,
                state,
            )
            entity_desc = copy(DEFAULT_SENSOR_DESCRIPTION)

        new_device = HMSensor(conf, entity_desc)
        devices.append(new_device)

    add_entities(devices, True)


class HMSensor(HMDevice, SensorEntity):
    """Representation of a HomeMatic sensor."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        # Does a cast exist for this class?
        name = self._hmdevice.__class__.__name__
        if name in HM_STATE_HA_CAST:
            return HM_STATE_HA_CAST[name].get(self._hm_get_state())

        # No cast, return original value
        return self._hm_get_state()

    def _init_data_struct(self):
        """Generate a data dictionary (self._data) from metadata."""
        if self._state:
            self._data.update({self._state: None})
        else:
            _LOGGER.critical("Unable to initialize sensor: %s", self._name)
