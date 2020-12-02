"""Support for 1-Wire environment sensors."""
from glob import glob
import logging
import os

from pi1wire import InvalidCRCException, UnsupportResponseException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_MOUNT_DIR,
    CONF_NAMES,
    CONF_TYPE_OWFS,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DEFAULT_OWSERVER_PORT,
    DEFAULT_SYSBUS_MOUNT_DIR,
    DOMAIN,
    SENSOR_TYPE_COUNT,
    SENSOR_TYPE_CURRENT,
    SENSOR_TYPE_HUMIDITY,
    SENSOR_TYPE_ILLUMINANCE,
    SENSOR_TYPE_MOISTURE,
    SENSOR_TYPE_PRESSURE,
    SENSOR_TYPE_TEMPERATURE,
    SENSOR_TYPE_VOLTAGE,
    SENSOR_TYPE_WETNESS,
)
from .onewire_entities import OneWireBaseEntity, OneWireProxyEntity
from .onewirehub import OneWireHub

_LOGGER = logging.getLogger(__name__)

DEVICE_SENSORS = {
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
}

DEVICE_SUPPORT_SYSBUS = ["10", "22", "28", "3B", "42"]

# EF sensors are usually hobbyboards specialized sensors.
# These can only be read by OWFS.  Currently this driver only supports them
# via owserver (network protocol)

HOBBYBOARD_EF = {
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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAMES): {cv.string: cv.string},
        vol.Optional(CONF_MOUNT_DIR, default=DEFAULT_SYSBUS_MOUNT_DIR): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_OWSERVER_PORT): cv.port,
    }
)


def hb_info_from_type(dev_type="std"):
    """Return the proper info array for the device type."""
    if "std" in dev_type:
        return DEVICE_SENSORS
    if "HobbyBoard" in dev_type:
        return HOBBYBOARD_EF


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up 1-Wire platform."""
    if config.get(CONF_HOST):
        config[CONF_TYPE] = CONF_TYPE_OWSERVER
    elif config[CONF_MOUNT_DIR] == DEFAULT_SYSBUS_MOUNT_DIR:
        config[CONF_TYPE] = CONF_TYPE_SYSBUS
    else:  # pragma: no cover
        # This part of the implementation does not conform to policy regarding 3rd-party libraries, and will not longer be updated.
        # https://developers.home-assistant.io/docs/creating_platform_code_review/#5-communication-with-devicesservices
        config[CONF_TYPE] = CONF_TYPE_OWFS

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up 1-Wire platform."""
    onewirehub = hass.data[DOMAIN][config_entry.unique_id]
    entities = await hass.async_add_executor_job(
        get_entities, onewirehub, config_entry.data
    )
    async_add_entities(entities, True)


def get_entities(onewirehub: OneWireHub, config):
    """Get a list of entities."""
    entities = []
    device_names = {}
    if CONF_NAMES in config:
        if isinstance(config[CONF_NAMES], dict):
            device_names = config[CONF_NAMES]

    conf_type = config[CONF_TYPE]
    # We have an owserver on a remote(or local) host/port
    if conf_type == CONF_TYPE_OWSERVER:
        for device in onewirehub.devices:
            family = device["family"]
            device_type = device["type"]
            device_id = os.path.split(os.path.split(device["path"])[0])[1]
            dev_type = "std"
            if "EF" in family:
                dev_type = "HobbyBoard"
                family = device_type

            if family not in hb_info_from_type(dev_type):
                _LOGGER.warning(
                    "Ignoring unknown family (%s) of sensor found for device: %s",
                    family,
                    device_id,
                )
                continue
            device_info = {
                "identifiers": {(DOMAIN, device_id)},
                "manufacturer": "Maxim Integrated",
                "model": device_type,
                "name": device_id,
            }
            for entity_specs in hb_info_from_type(dev_type)[family]:
                if entity_specs["type"] == SENSOR_TYPE_MOISTURE:
                    s_id = entity_specs["path"].split(".")[1]
                    is_leaf = int(
                        onewirehub.owproxy.read(
                            f"{device['path']}moisture/is_leaf.{s_id}"
                        ).decode()
                    )
                    if is_leaf:
                        entity_specs["type"] = SENSOR_TYPE_WETNESS
                        entity_specs["name"] = f"Wetness {s_id}"
                entity_path = os.path.join(
                    os.path.split(device["path"])[0], entity_specs["path"]
                )
                entities.append(
                    OneWireProxySensor(
                        device_id=device_id,
                        device_name=device_names.get(device_id, device_id),
                        device_info=device_info,
                        entity_path=entity_path,
                        entity_specs=entity_specs,
                        owproxy=onewirehub.owproxy,
                    )
                )

    # We have a raw GPIO ow sensor on a Pi
    elif conf_type == CONF_TYPE_SYSBUS:
        base_dir = config[CONF_MOUNT_DIR]
        _LOGGER.debug("Initializing using SysBus %s", base_dir)
        for p1sensor in onewirehub.devices:
            family = p1sensor.mac_address[:2]
            sensor_id = f"{family}-{p1sensor.mac_address[2:]}"
            if family not in DEVICE_SUPPORT_SYSBUS:
                _LOGGER.warning(
                    "Ignoring unknown family (%s) of sensor found for device: %s",
                    family,
                    sensor_id,
                )
                continue

            device_info = {
                "identifiers": {(DOMAIN, sensor_id)},
                "manufacturer": "Maxim Integrated",
                "model": family,
                "name": sensor_id,
            }
            device_file = f"/sys/bus/w1/devices/{sensor_id}/w1_slave"
            entities.append(
                OneWireDirectSensor(
                    device_names.get(sensor_id, sensor_id),
                    device_file,
                    device_info,
                    p1sensor,
                )
            )
        if not entities:
            _LOGGER.error(
                "No onewire sensor found. Check if dtoverlay=w1-gpio "
                "is in your /boot/config.txt. "
                "Check the mount_dir parameter if it's defined"
            )

    # We have an owfs mounted
    else:  # pragma: no cover
        # This part of the implementation does not conform to policy regarding 3rd-party libraries, and will not longer be updated.
        # https://developers.home-assistant.io/docs/creating_platform_code_review/#5-communication-with-devicesservices
        base_dir = config[CONF_MOUNT_DIR]
        _LOGGER.debug("Initializing using OWFS %s", base_dir)
        _LOGGER.warning(
            "The OWFS implementation of 1-Wire sensors is deprecated, "
            "and should be migrated to OWServer (on localhost:4304). "
            "If migration to OWServer is not feasible on your installation, "
            "please raise an issue at https://github.com/home-assistant/core/issues/new"
            "?title=Unable%20to%20migrate%20onewire%20from%20OWFS%20to%20OWServer",
        )
        for family_file_path in glob(os.path.join(base_dir, "*", "family")):
            with open(family_file_path) as family_file:
                family = family_file.read()
            if "EF" in family:
                continue
            if family in DEVICE_SENSORS:
                for sensor_key, sensor_value in DEVICE_SENSORS[family].items():
                    sensor_id = os.path.split(os.path.split(family_file_path)[0])[1]
                    device_file = os.path.join(
                        os.path.split(family_file_path)[0], sensor_value
                    )
                    entities.append(
                        OneWireOWFSSensor(
                            device_names.get(sensor_id, sensor_id),
                            device_file,
                            sensor_key,
                        )
                    )

    return entities


class OneWireProxySensor(OneWireProxyEntity):
    """Implementation of a 1-Wire sensor connected through owserver."""

    @property
    def state(self) -> StateType:
        """Return the state of the entity."""
        return self._state


class OneWireDirectSensor(OneWireBaseEntity):
    """Implementation of a 1-Wire sensor directly connected to RPI GPIO."""

    def __init__(self, name, device_file, device_info, owsensor):
        """Initialize the sensor."""
        super().__init__(name, device_file, "temperature", "Temperature", device_info)
        self._owsensor = owsensor

    @property
    def state(self) -> StateType:
        """Return the state of the entity."""
        return self._state

    def update(self):
        """Get the latest data from the device."""
        value = None
        try:
            self._value_raw = self._owsensor.get_temperature()
            value = round(float(self._value_raw), 1)
        except (
            FileNotFoundError,
            InvalidCRCException,
            UnsupportResponseException,
        ) as ex:
            _LOGGER.warning("Cannot read from sensor %s: %s", self._device_file, ex)
        self._state = value


class OneWireOWFSSensor(OneWireBaseEntity):  # pragma: no cover
    """Implementation of a 1-Wire sensor through owfs.

    This part of the implementation does not conform to policy regarding 3rd-party libraries, and will not longer be updated.
    https://developers.home-assistant.io/docs/creating_platform_code_review/#5-communication-with-devicesservices
    """

    @property
    def state(self) -> StateType:
        """Return the state of the entity."""
        return self._state

    def _read_value_raw(self):
        """Read the value as it is returned by the sensor."""
        with open(self._device_file) as ds_device_file:
            lines = ds_device_file.readlines()
        return lines

    def update(self):
        """Get the latest data from the device."""
        value = None
        try:
            value_read = self._read_value_raw()
            if len(value_read) == 1:
                value = round(float(value_read[0]), 1)
                self._value_raw = float(value_read[0])
        except ValueError:
            _LOGGER.warning("Invalid value read from %s", self._device_file)
        except FileNotFoundError:
            _LOGGER.warning("Cannot read from sensor: %s", self._device_file)

        self._state = value
