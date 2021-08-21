"""Support for 1-Wire environment sensors."""
from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
import logging
import os
from types import MappingProxyType
from typing import Any

from pi1wire import InvalidCRCException, OneWireInterface, UnsupportResponseException

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_MOUNT_DIR,
    CONF_NAMES,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DOMAIN,
    PRESSURE_CBAR,
    READ_MODE_FLOAT,
    READ_MODE_INT,
)
from .onewire_entities import (
    OneWireBaseEntity,
    OneWireEntityDescription,
    OneWireProxyEntity,
)
from .model import DeviceComponentDescription
from .onewire_entities import OneWireBaseEntity, OneWireProxyEntity
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

DEVICE_SENSORS: dict[str, list[DeviceComponentDescription]] = {
    # Family : { SensorType: owfs path }
    "10": [
        {"path": "temperature", "name": "Temperature", "type": SENSOR_TYPE_TEMPERATURE}
    ],
    "12": [
        {
            "path": "TAI8570/temperature",
            "name": "Temperature",
            "type": SENSOR_TYPE_TEMPERATURE,
            "default_disabled": True,
        },
        {
            "path": "TAI8570/pressure",
            "name": "Pressure",
            "type": SENSOR_TYPE_PRESSURE,
            "default_disabled": True,
        },
    ],
    "22": [
        {"path": "temperature", "name": "Temperature", "type": SENSOR_TYPE_TEMPERATURE}
    ],
    "26": [
        {"path": "temperature", "name": "Temperature", "type": SENSOR_TYPE_TEMPERATURE},
        {
            "path": "humidity",
            "name": "Humidity",
            "type": SENSOR_TYPE_HUMIDITY,
            "default_disabled": True,
        },
        {
            "path": "HIH3600/humidity",
            "name": "Humidity HIH3600",
            "type": SENSOR_TYPE_HUMIDITY,
            "default_disabled": True,
        },
        {
            "path": "HIH4000/humidity",
            "name": "Humidity HIH4000",
            "type": SENSOR_TYPE_HUMIDITY,
            "default_disabled": True,
        },
        {
            "path": "HIH5030/humidity",
            "name": "Humidity HIH5030",
            "type": SENSOR_TYPE_HUMIDITY,
            "default_disabled": True,
        },
        {
            "path": "HTM1735/humidity",
            "name": "Humidity HTM1735",
            "type": SENSOR_TYPE_HUMIDITY,
            "default_disabled": True,
        },
        {
            "path": "B1-R1-A/pressure",
            "name": "Pressure",
            "type": SENSOR_TYPE_PRESSURE,
            "default_disabled": True,
        },
        {
            "path": "S3-R1-A/illuminance",
            "name": "Illuminance",
            "type": SENSOR_TYPE_ILLUMINANCE,
            "default_disabled": True,
        },
        {
            "path": "VAD",
            "name": "Voltage VAD",
            "type": SENSOR_TYPE_VOLTAGE,
            "default_disabled": True,
        },
        {
            "path": "VDD",
            "name": "Voltage VDD",
            "type": SENSOR_TYPE_VOLTAGE,
            "default_disabled": True,
        },
        {
            "path": "IAD",
            "name": "Current",
            "type": SENSOR_TYPE_CURRENT,
            "default_disabled": True,
        },
    ],
    "28": [
        {"path": "temperature", "name": "Temperature", "type": SENSOR_TYPE_TEMPERATURE}
    ],
    "3B": [
        {"path": "temperature", "name": "Temperature", "type": SENSOR_TYPE_TEMPERATURE}
    ],
    "42": [
        {"path": "temperature", "name": "Temperature", "type": SENSOR_TYPE_TEMPERATURE}
    ],
    "1D": [
        {"path": "counter.A", "name": "Counter A", "type": SENSOR_TYPE_COUNT},
        {"path": "counter.B", "name": "Counter B", "type": SENSOR_TYPE_COUNT},
    ],
    "EF": [],  # "HobbyBoard": special
    "7E": [],  # "EDS": special
}

DEVICE_SUPPORT_SYSBUS = ["10", "22", "28", "3B", "42"]

# EF sensors are usually hobbyboards specialized sensors.
# These can only be read by OWFS.  Currently this driver only supports them
# via owserver (network protocol)

HOBBYBOARD_EF: dict[str, list[DeviceComponentDescription]] = {
    "HobbyBoards_EF": [
        {
            "path": "humidity/humidity_corrected",
            "name": "Humidity",
            "type": SENSOR_TYPE_HUMIDITY,
        },
        {
            "path": "humidity/humidity_raw",
            "name": "Humidity Raw",
            "type": SENSOR_TYPE_HUMIDITY,
        },
        {
            "path": "humidity/temperature",
            "name": "Temperature",
            "type": SENSOR_TYPE_TEMPERATURE,
        },
    ],
    "HB_MOISTURE_METER": [
        {
            "path": "moisture/sensor.0",
            "name": "Moisture 0",
            "type": SENSOR_TYPE_MOISTURE,
        },
        {
            "path": "moisture/sensor.1",
            "name": "Moisture 1",
            "type": SENSOR_TYPE_MOISTURE,
        },
        {
            "path": "moisture/sensor.2",
            "name": "Moisture 2",
            "type": SENSOR_TYPE_MOISTURE,
        },
        {
            "path": "moisture/sensor.3",
            "name": "Moisture 3",
            "type": SENSOR_TYPE_MOISTURE,
        },
    ],
}

# 7E sensors are special sensors by Embedded Data Systems

EDS_SENSORS: dict[str, list[DeviceComponentDescription]] = {
    "EDS0066": [
        {
            "path": "EDS0066/temperature",
            "name": "Temperature",
            "type": SENSOR_TYPE_TEMPERATURE,
        },
        {
            "path": "EDS0066/pressure",
            "name": "Pressure",
            "type": SENSOR_TYPE_PRESSURE,
        },
    ],
    "EDS0068": [
        {
            "path": "EDS0068/temperature",
            "name": "Temperature",
            "type": SENSOR_TYPE_TEMPERATURE,
        },
        {
            "path": "EDS0068/pressure",
            "name": "Pressure",
            "type": SENSOR_TYPE_PRESSURE,
        },
        {
            "path": "EDS0068/light",
            "name": "Illuminance",
            "type": SENSOR_TYPE_ILLUMINANCE,
        },
        {
            "path": "EDS0068/humidity",
            "name": "Humidity",
            "type": SENSOR_TYPE_HUMIDITY,
        },
    ],
}


def get_sensor_types(device_sub_type: str) -> dict[str, Any]:
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
) -> list[OneWireBaseEntity]:
    """Get a list of entities."""
    if not onewirehub.devices:
        return []

    entities: list[OneWireBaseEntity] = []
    device_names = {}
    if CONF_NAMES in config and isinstance(config[CONF_NAMES], dict):
        device_names = config[CONF_NAMES]

    conf_type = config[CONF_TYPE]
    # We have an owserver on a remote(or local) host/port
    if conf_type == CONF_TYPE_OWSERVER:
        assert onewirehub.owproxy
        for device in onewirehub.devices:
            family = device["family"]
            device_type = device["type"]
            device_id = os.path.split(os.path.split(device["path"])[0])[1]
            device_sub_type = "std"
            device_path = device["path"]
            if "EF" in family:
                device_sub_type = "HobbyBoard"
                family = device_type
            elif "7E" in family:
                device_sub_type = "EDS"
                family = onewirehub.owproxy.read(f"{device_path}device_type").decode()

            if family not in get_sensor_types(device_sub_type):
                _LOGGER.warning(
                    "Ignoring unknown family (%s) of sensor found for device: %s",
                    family,
                    device_id,
                )
                continue
            device_info: DeviceInfo = {
                ATTR_IDENTIFIERS: {(DOMAIN, device_id)},
                ATTR_MANUFACTURER: "Maxim Integrated",
                ATTR_MODEL: device_type,
                ATTR_NAME: device_id,
            }
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
                    os.path.split(device["path"])[0], description.key
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
        base_dir = config[CONF_MOUNT_DIR]
        _LOGGER.debug("Initializing using SysBus %s", base_dir)
        for p1sensor in onewirehub.devices:
            family = p1sensor.mac_address[:2]
            device_id = f"{family}-{p1sensor.mac_address[2:]}"
            if family not in DEVICE_SUPPORT_SYSBUS:
                _LOGGER.warning(
                    "Ignoring unknown family (%s) of sensor found for device: %s",
                    family,
                    device_id,
                )
                continue

            device_info = {
                ATTR_IDENTIFIERS: {(DOMAIN, sensor_id)},
                ATTR_MANUFACTURER: "Maxim Integrated",
                ATTR_MODEL: family,
                ATTR_NAME: sensor_id,
            }
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
        if not entities:
            _LOGGER.error(
                "No onewire sensor found. Check if dtoverlay=w1-gpio "
                "is in your /boot/config.txt. "
                "Check the mount_dir parameter if it's defined"
            )

    return entities


class OneWireSensor(OneWireBaseEntity, SensorEntity):
    """Mixin for sensor specific attributes."""

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement


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
        name: str,
        device_file: str,
        device_info: DeviceInfo,
        owsensor: OneWireInterface,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            name,
            device_file,
            "temperature",
            "Temperature",
            device_info,
            False,
            device_file,
        )
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
            _LOGGER.warning("Cannot read from sensor %s: %s", self._device_file, ex)
            self._state = None
