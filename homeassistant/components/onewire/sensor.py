"""Support for 1-Wire environment sensors."""
from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
import logging
import os
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from pi1wire import InvalidCRCException, OneWireInterface, UnsupportResponseException

from homeassistant.components.onewire.model import (
    OWDirectDeviceDescription,
    OWServerDeviceDescription,
)
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_TYPE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_POTENTIAL_VOLT,
    LIGHT_LUX,
    PERCENTAGE,
    PRESSURE_CBAR,
    PRESSURE_MBAR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_NAMES,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DOMAIN,
    READ_MODE_FLOAT,
    READ_MODE_INT,
)
from .onewire_entities import (
    OneWireBaseEntity,
    OneWireEntityDescription,
    OneWireProxyEntity,
)
from .onewirehub import OneWireHub


@dataclass
class OneWireSensorEntityDescription(OneWireEntityDescription, SensorEntityDescription):
    """Class describing OneWire sensor entities."""


SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION = OneWireSensorEntityDescription(
    key="temperature",
    device_class=DEVICE_CLASS_TEMPERATURE,
    name="Temperature",
    native_unit_of_measurement=TEMP_CELSIUS,
    read_mode=READ_MODE_FLOAT,
    state_class=STATE_CLASS_MEASUREMENT,
)

_LOGGER = logging.getLogger(__name__)


DEVICE_SENSORS: dict[str, tuple[OneWireSensorEntityDescription, ...]] = {
    "10": (SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION,),
    "12": (
        OneWireSensorEntityDescription(
            key="TAI8570/temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            entity_registry_enabled_default=False,
            name="Temperature",
            native_unit_of_measurement=TEMP_CELSIUS,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="TAI8570/pressure",
            device_class=DEVICE_CLASS_PRESSURE,
            entity_registry_enabled_default=False,
            name="Pressure",
            native_unit_of_measurement=PRESSURE_MBAR,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    ),
    "22": (SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION,),
    "26": (
        SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION,
        OneWireSensorEntityDescription(
            key="humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            entity_registry_enabled_default=False,
            name="Humidity",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="HIH3600/humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            entity_registry_enabled_default=False,
            name="Humidity HIH3600",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="HIH4000/humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            entity_registry_enabled_default=False,
            name="Humidity HIH4000",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="HIH5030/humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            entity_registry_enabled_default=False,
            name="Humidity HIH5030",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="HTM1735/humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            entity_registry_enabled_default=False,
            name="Humidity HTM1735",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="B1-R1-A/pressure",
            device_class=DEVICE_CLASS_PRESSURE,
            entity_registry_enabled_default=False,
            name="Pressure",
            native_unit_of_measurement=PRESSURE_MBAR,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="S3-R1-A/illuminance",
            device_class=DEVICE_CLASS_ILLUMINANCE,
            entity_registry_enabled_default=False,
            name="Illuminance",
            native_unit_of_measurement=LIGHT_LUX,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="VAD",
            device_class=DEVICE_CLASS_VOLTAGE,
            entity_registry_enabled_default=False,
            name="Voltage VAD",
            native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="VDD",
            device_class=DEVICE_CLASS_VOLTAGE,
            entity_registry_enabled_default=False,
            name="Voltage VDD",
            native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="vis",
            device_class=DEVICE_CLASS_VOLTAGE,
            entity_registry_enabled_default=False,
            name="vis",
            native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    ),
    "28": (SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION,),
    "3B": (SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION,),
    "42": (SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION,),
    "1D": (
        OneWireSensorEntityDescription(
            key="counter.A",
            name="Counter A",
            native_unit_of_measurement="count",
            read_mode=READ_MODE_INT,
            state_class=STATE_CLASS_TOTAL_INCREASING,
        ),
        OneWireSensorEntityDescription(
            key="counter.B",
            name="Counter B",
            native_unit_of_measurement="count",
            read_mode=READ_MODE_INT,
            state_class=STATE_CLASS_TOTAL_INCREASING,
        ),
    ),
}

# EF sensors are usually hobbyboards specialized sensors.
# These can only be read by OWFS.  Currently this driver only supports them
# via owserver (network protocol)

HOBBYBOARD_EF: dict[str, tuple[OneWireSensorEntityDescription, ...]] = {
    "HobbyBoards_EF": (
        OneWireSensorEntityDescription(
            key="humidity/humidity_corrected",
            device_class=DEVICE_CLASS_HUMIDITY,
            name="Humidity",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="humidity/humidity_raw",
            device_class=DEVICE_CLASS_HUMIDITY,
            name="Humidity Raw",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="humidity/temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            name="Temperature",
            native_unit_of_measurement=TEMP_CELSIUS,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    ),
    "HB_MOISTURE_METER": (
        OneWireSensorEntityDescription(
            key="moisture/sensor.0",
            device_class=DEVICE_CLASS_PRESSURE,
            name="Moisture 0",
            native_unit_of_measurement=PRESSURE_CBAR,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="moisture/sensor.1",
            device_class=DEVICE_CLASS_PRESSURE,
            name="Moisture 1",
            native_unit_of_measurement=PRESSURE_CBAR,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="moisture/sensor.2",
            device_class=DEVICE_CLASS_PRESSURE,
            name="Moisture 2",
            native_unit_of_measurement=PRESSURE_CBAR,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="moisture/sensor.3",
            device_class=DEVICE_CLASS_PRESSURE,
            name="Moisture 3",
            native_unit_of_measurement=PRESSURE_CBAR,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    ),
}

# 7E sensors are special sensors by Embedded Data Systems

EDS_SENSORS: dict[str, tuple[OneWireSensorEntityDescription, ...]] = {
    "EDS0066": (
        OneWireSensorEntityDescription(
            key="EDS0066/temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            name="Temperature",
            native_unit_of_measurement=TEMP_CELSIUS,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="EDS0066/pressure",
            device_class=DEVICE_CLASS_PRESSURE,
            name="Pressure",
            native_unit_of_measurement=PRESSURE_MBAR,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    ),
    "EDS0068": (
        OneWireSensorEntityDescription(
            key="EDS0068/temperature",
            device_class=DEVICE_CLASS_TEMPERATURE,
            name="Temperature",
            native_unit_of_measurement=TEMP_CELSIUS,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="EDS0068/pressure",
            device_class=DEVICE_CLASS_PRESSURE,
            name="Pressure",
            native_unit_of_measurement=PRESSURE_MBAR,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="EDS0068/light",
            device_class=DEVICE_CLASS_ILLUMINANCE,
            name="Illuminance",
            native_unit_of_measurement=LIGHT_LUX,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="EDS0068/humidity",
            device_class=DEVICE_CLASS_HUMIDITY,
            name="Humidity",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
    ),
}


def get_sensor_types(
    device_sub_type: str,
) -> dict[str, tuple[OneWireSensorEntityDescription, ...]]:
    """Return the proper info array for the device type."""
    if "HobbyBoard" in device_sub_type:
        return HOBBYBOARD_EF
    if "EDS" in device_sub_type:
        return EDS_SENSORS
    return DEVICE_SENSORS


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 1-Wire platform."""
    onewirehub = hass.data[DOMAIN][config_entry.entry_id]
    entities = await hass.async_add_executor_job(
        get_entities, onewirehub, config_entry.data
    )
    async_add_entities(entities, True)


def get_entities(
    onewirehub: OneWireHub, config: MappingProxyType[str, Any]
) -> list[SensorEntity]:
    """Get a list of entities."""
    if not onewirehub.devices:
        return []

    entities: list[SensorEntity] = []
    device_names = {}
    if CONF_NAMES in config and isinstance(config[CONF_NAMES], dict):
        device_names = config[CONF_NAMES]

    conf_type = config[CONF_TYPE]
    # We have an owserver on a remote(or local) host/port
    if conf_type == CONF_TYPE_OWSERVER:
        assert onewirehub.owproxy
        for device in onewirehub.devices:
            if TYPE_CHECKING:
                assert isinstance(device, OWServerDeviceDescription)
            family = device.family
            device_type = device.type
            device_id = device.id
            device_info = device.device_info
            device_sub_type = "std"
            device_path = device.path
            if "EF" in family:
                device_sub_type = "HobbyBoard"
                family = device_type
            elif "7E" in family:
                device_sub_type = "EDS"
                family = device_type

            if family not in get_sensor_types(device_sub_type):
                continue
            for description in get_sensor_types(device_sub_type)[family]:
                if description.key.startswith("moisture/"):
                    s_id = description.key.split(".")[1]
                    is_leaf = int(
                        onewirehub.owproxy.read(
                            f"{device_path}moisture/is_leaf.{s_id}"
                        ).decode()
                    )
                    if is_leaf:
                        description = copy.deepcopy(description)
                        description.device_class = DEVICE_CLASS_HUMIDITY
                        description.native_unit_of_measurement = PERCENTAGE
                        description.name = f"Wetness {s_id}"
                device_file = os.path.join(
                    os.path.split(device.path)[0], description.key
                )
                name = f"{device_names.get(device_id, device_id)} {description.name}"
                entities.append(
                    OneWireProxySensor(
                        description=description,
                        device_id=device_id,
                        device_file=device_file,
                        device_info=device_info,
                        name=name,
                        owproxy=onewirehub.owproxy,
                    )
                )

    # We have a raw GPIO ow sensor on a Pi
    elif conf_type == CONF_TYPE_SYSBUS:
        for device in onewirehub.devices:
            if TYPE_CHECKING:
                assert isinstance(device, OWDirectDeviceDescription)
            p1sensor: OneWireInterface = device.interface
            family = p1sensor.mac_address[:2]
            device_id = f"{family}-{p1sensor.mac_address[2:]}"
            device_info = device.device_info
            description = SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION
            device_file = f"/sys/bus/w1/devices/{device_id}/w1_slave"
            name = f"{device_names.get(device_id, device_id)} {description.name}"
            entities.append(
                OneWireDirectSensor(
                    description=description,
                    device_id=device_id,
                    device_file=device_file,
                    device_info=device_info,
                    name=name,
                    owsensor=p1sensor,
                )
            )

    return entities


class OneWireSensor(OneWireBaseEntity, SensorEntity):
    """Mixin for sensor specific attributes."""

    entity_description: OneWireSensorEntityDescription


class OneWireProxySensor(OneWireProxyEntity, OneWireSensor):
    """Implementation of a 1-Wire sensor connected through owserver."""

    entity_description: OneWireSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return self._state


class OneWireDirectSensor(OneWireSensor):
    """Implementation of a 1-Wire sensor directly connected to RPI GPIO."""

    def __init__(
        self,
        description: OneWireSensorEntityDescription,
        device_id: str,
        device_info: DeviceInfo,
        device_file: str,
        name: str,
        owsensor: OneWireInterface,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            description=description,
            device_id=device_id,
            device_info=device_info,
            device_file=device_file,
            name=name,
        )
        self._attr_unique_id = device_file
        self._owsensor = owsensor

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return self._state

    async def get_temperature(self) -> float:
        """Get the latest data from the device."""
        attempts = 1
        while True:
            try:
                return await self.hass.async_add_executor_job(
                    self._owsensor.get_temperature
                )
            except UnsupportResponseException as ex:
                _LOGGER.debug(
                    "Cannot read from sensor %s (retry attempt %s): %s",
                    self._device_file,
                    attempts,
                    ex,
                )
                await asyncio.sleep(0.2)
                attempts += 1
                if attempts > 10:
                    raise

    async def async_update(self) -> None:
        """Get the latest data from the device."""
        try:
            self._value_raw = await self.get_temperature()
            self._state = round(self._value_raw, 1)
        except (
            FileNotFoundError,
            InvalidCRCException,
            UnsupportResponseException,
        ) as ex:
            _LOGGER.warning(
                "Cannot read from sensor %s: %s",
                self._device_file,
                ex,
            )
            self._state = None
