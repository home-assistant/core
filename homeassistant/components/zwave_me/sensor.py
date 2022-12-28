"""Representation of a sensorMultilevel."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from zwave_me_ws import ZWaveMeData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZWaveMeController, ZWaveMeEntity
from .const import DOMAIN, ZWaveMePlatform


@dataclass
class ZWaveMeSensorEntityDescription(SensorEntityDescription):
    """Class describing ZWaveMeSensor sensor entities."""

    value: Callable = lambda value: value


SENSORS_MAP: dict[str, ZWaveMeSensorEntityDescription] = {
    "barometer": ZWaveMeSensorEntityDescription(
        key="barometer",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "co": ZWaveMeSensorEntityDescription(
        key="co",
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "co2": ZWaveMeSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "humidity": ZWaveMeSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "luminosity": ZWaveMeSensorEntityDescription(
        key="luminosity",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "meterElectric_ampere": ZWaveMeSensorEntityDescription(
        key="meterElectric_ampere",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "meterElectric_kilowatt_hour": ZWaveMeSensorEntityDescription(
        key="meterElectric_kilowatt_hour",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "meterElectric_power_factor": ZWaveMeSensorEntityDescription(
        key="meterElectric_power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda value: float(value) * 100,
    ),
    "meterElectric_voltage": ZWaveMeSensorEntityDescription(
        key="meterElectric_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "meterElectric_watt": ZWaveMeSensorEntityDescription(
        key="meterElectric_watt",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "temperature": ZWaveMeSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "generic": ZWaveMeSensorEntityDescription(
        key="generic",
    ),
}
DEVICE_NAME = ZWaveMePlatform.SENSOR


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    @callback
    def add_new_device(new_device: ZWaveMeData) -> None:
        controller: ZWaveMeController = hass.data[DOMAIN][config_entry.entry_id]
        description = SENSORS_MAP.get(new_device.probeType, SENSORS_MAP["generic"])
        sensor = ZWaveMeSensor(controller, new_device, description)

        async_add_entities(
            [
                sensor,
            ]
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"ZWAVE_ME_NEW_{DEVICE_NAME.upper()}", add_new_device
        )
    )


class ZWaveMeSensor(ZWaveMeEntity, SensorEntity):
    """Representation of a ZWaveMe sensor."""

    entity_description: ZWaveMeSensorEntityDescription

    def __init__(
        self,
        controller: ZWaveMeController,
        device: ZWaveMeData,
        description: ZWaveMeSensorEntityDescription,
    ) -> None:
        """Initialize the device."""
        super().__init__(controller=controller, device=device)
        self.entity_description = description

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.entity_description.value(self.device.level)
