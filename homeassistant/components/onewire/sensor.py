"""Support for 1-Wire environment sensors."""
from __future__ import annotations

from collections.abc import Callable, Mapping
import copy
from dataclasses import dataclass
import logging
import os
from types import MappingProxyType
from typing import Any

from pyownet import protocol

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
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    DEVICE_KEYS_0_3,
    DEVICE_KEYS_A_B,
    DOMAIN,
    OPTION_ENTRY_DEVICE_OPTIONS,
    OPTION_ENTRY_SENSOR_PRECISION,
    PRECISION_MAPPING_FAMILY_28,
    READ_MODE_FLOAT,
    READ_MODE_INT,
)
from .onewire_entities import OneWireEntity, OneWireEntityDescription
from .onewirehub import OneWireHub


@dataclass
class OneWireSensorEntityDescription(OneWireEntityDescription, SensorEntityDescription):
    """Class describing OneWire sensor entities."""

    override_key: Callable[[str, Mapping[str, Any]], str] | None = None


def _get_sensor_precision_family_28(device_id: str, options: Mapping[str, Any]) -> str:
    """Get precision form config flow options."""
    precision: str = (
        options.get(OPTION_ENTRY_DEVICE_OPTIONS, {})
        .get(device_id, {})
        .get(OPTION_ENTRY_SENSOR_PRECISION, "temperature")
    )
    if precision in PRECISION_MAPPING_FAMILY_28:
        return precision
    _LOGGER.warning(
        "Invalid sensor precision `%s` for device `%s`: reverting to default",
        precision,
        device_id,
    )
    return "temperature"


SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION = OneWireSensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    name="Temperature",
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    read_mode=READ_MODE_FLOAT,
    state_class=SensorStateClass.MEASUREMENT,
)

_LOGGER = logging.getLogger(__name__)


DEVICE_SENSORS: dict[str, tuple[OneWireSensorEntityDescription, ...]] = {
    "10": (SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION,),
    "12": (
        OneWireSensorEntityDescription(
            key="TAI8570/temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            entity_registry_enabled_default=False,
            name="Temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="TAI8570/pressure",
            device_class=SensorDeviceClass.PRESSURE,
            entity_registry_enabled_default=False,
            name="Pressure",
            native_unit_of_measurement=UnitOfPressure.MBAR,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    "22": (SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION,),
    "26": (
        SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION,
        OneWireSensorEntityDescription(
            key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            entity_registry_enabled_default=False,
            name="Humidity",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="HIH3600/humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            entity_registry_enabled_default=False,
            name="Humidity HIH3600",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="HIH4000/humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            entity_registry_enabled_default=False,
            name="Humidity HIH4000",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="HIH5030/humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            entity_registry_enabled_default=False,
            name="Humidity HIH5030",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="HTM1735/humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            entity_registry_enabled_default=False,
            name="Humidity HTM1735",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="B1-R1-A/pressure",
            device_class=SensorDeviceClass.PRESSURE,
            entity_registry_enabled_default=False,
            name="Pressure",
            native_unit_of_measurement=UnitOfPressure.MBAR,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="S3-R1-A/illuminance",
            device_class=SensorDeviceClass.ILLUMINANCE,
            entity_registry_enabled_default=False,
            name="Illuminance",
            native_unit_of_measurement=LIGHT_LUX,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="VAD",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_registry_enabled_default=False,
            name="Voltage VAD",
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="VDD",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_registry_enabled_default=False,
            name="Voltage VDD",
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="vis",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_registry_enabled_default=False,
            name="vis",
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    "28": (
        OneWireSensorEntityDescription(
            key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            name="Temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            override_key=_get_sensor_precision_family_28,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    "30": (
        SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION,
        OneWireSensorEntityDescription(
            key="typeX/temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            entity_registry_enabled_default=False,
            name="Thermocouple temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            read_mode=READ_MODE_FLOAT,
            override_key=lambda d, o: "typeK/temperature",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="volt",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_registry_enabled_default=False,
            name="Voltage",
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="vis",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_registry_enabled_default=False,
            name="vis",
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    "3B": (SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION,),
    "42": (SIMPLE_TEMPERATURE_SENSOR_DESCRIPTION,),
    "1D": tuple(
        OneWireSensorEntityDescription(
            key=f"counter.{id}",
            name=f"Counter {id}",
            native_unit_of_measurement="count",
            read_mode=READ_MODE_INT,
            state_class=SensorStateClass.TOTAL_INCREASING,
        )
        for id in DEVICE_KEYS_A_B
    ),
}

# EF sensors are usually hobbyboards specialized sensors.

HOBBYBOARD_EF: dict[str, tuple[OneWireSensorEntityDescription, ...]] = {
    "HobbyBoards_EF": (
        OneWireSensorEntityDescription(
            key="humidity/humidity_corrected",
            device_class=SensorDeviceClass.HUMIDITY,
            name="Humidity",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="humidity/humidity_raw",
            device_class=SensorDeviceClass.HUMIDITY,
            name="Humidity Raw",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="humidity/temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            name="Temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    "HB_MOISTURE_METER": tuple(
        OneWireSensorEntityDescription(
            key=f"moisture/sensor.{id}",
            device_class=SensorDeviceClass.PRESSURE,
            name=f"Moisture {id}",
            native_unit_of_measurement=UnitOfPressure.CBAR,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        )
        for id in DEVICE_KEYS_0_3
    ),
}

# 7E sensors are special sensors by Embedded Data Systems

EDS_SENSORS: dict[str, tuple[OneWireSensorEntityDescription, ...]] = {
    "EDS0066": (
        OneWireSensorEntityDescription(
            key="EDS0066/temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            name="Temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="EDS0066/pressure",
            device_class=SensorDeviceClass.PRESSURE,
            name="Pressure",
            native_unit_of_measurement=UnitOfPressure.MBAR,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    "EDS0068": (
        OneWireSensorEntityDescription(
            key="EDS0068/temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            name="Temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="EDS0068/pressure",
            device_class=SensorDeviceClass.PRESSURE,
            name="Pressure",
            native_unit_of_measurement=UnitOfPressure.MBAR,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="EDS0068/light",
            device_class=SensorDeviceClass.ILLUMINANCE,
            name="Illuminance",
            native_unit_of_measurement=LIGHT_LUX,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        OneWireSensorEntityDescription(
            key="EDS0068/humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            name="Humidity",
            native_unit_of_measurement=PERCENTAGE,
            read_mode=READ_MODE_FLOAT,
            state_class=SensorStateClass.MEASUREMENT,
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
    onewire_hub = hass.data[DOMAIN][config_entry.entry_id]
    entities = await hass.async_add_executor_job(
        get_entities, onewire_hub, config_entry.options
    )
    async_add_entities(entities, True)


def get_entities(
    onewire_hub: OneWireHub, options: MappingProxyType[str, Any]
) -> list[OneWireSensor]:
    """Get a list of entities."""
    if not onewire_hub.devices:
        return []

    entities: list[OneWireSensor] = []
    assert onewire_hub.owproxy
    for device in onewire_hub.devices:
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
                    onewire_hub.owproxy.read(
                        f"{device_path}moisture/is_leaf.{s_id}"
                    ).decode()
                )
                if is_leaf:
                    description = copy.deepcopy(description)
                    description.device_class = SensorDeviceClass.HUMIDITY
                    description.native_unit_of_measurement = PERCENTAGE
                    description.name = f"Wetness {s_id}"
            override_key = None
            if description.override_key:
                override_key = description.override_key(device_id, options)
            device_file = os.path.join(
                os.path.split(device.path)[0],
                override_key or description.key,
            )
            name = f"{device_id} {description.name}"
            if family == "12":
                # We need to check if there is TAI8570 plugged in
                try:
                    onewire_hub.owproxy.read(device_file)
                except protocol.OwnetError as err:
                    _LOGGER.debug(
                        "Ignoring unreachable sensor %s",
                        device_file,
                        exc_info=err,
                    )
                    continue
            entities.append(
                OneWireSensor(
                    description=description,
                    device_id=device_id,
                    device_file=device_file,
                    device_info=device_info,
                    name=name,
                    owproxy=onewire_hub.owproxy,
                )
            )
    return entities


class OneWireSensor(OneWireEntity, SensorEntity):
    """Implementation of a 1-Wire sensor."""

    entity_description: OneWireSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return self._state
