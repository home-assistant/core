"""Support for 1-Wire environment sensors."""
from glob import glob
import logging
import os
import time

from pyownet import protocol
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    ELECTRICAL_CURRENT_AMPERE,
    LIGHT_LUX,
    PERCENTAGE,
    TEMP_CELSIUS,
    VOLT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_MOUNT_DIR,
    CONF_NAMES,
    DEFAULT_OWSERVER_PORT,
    DEFAULT_SYSBUS_MOUNT_DIR,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_SENSORS = {
    # Family : { SensorType: owfs path }
    "10": {"temperature": "temperature"},
    "12": {"temperature": "TAI8570/temperature", "pressure": "TAI8570/pressure"},
    "22": {"temperature": "temperature"},
    "26": {
        "temperature": "temperature",
        "humidity": "humidity",
        "humidity_hih3600": "HIH3600/humidity",
        "humidity_hih4000": "HIH4000/humidity",
        "humidity_hih5030": "HIH5030/humidity",
        "humidity_htm1735": "HTM1735/humidity",
        "pressure": "B1-R1-A/pressure",
        "illuminance": "S3-R1-A/illuminance",
        "voltage_VAD": "VAD",
        "voltage_VDD": "VDD",
        "current": "IAD",
    },
    "28": {"temperature": "temperature"},
    "3B": {"temperature": "temperature"},
    "42": {"temperature": "temperature"},
    "1D": {"counter_a": "counter.A", "counter_b": "counter.B"},
    "EF": {"HobbyBoard": "special"},
}

# EF sensors are usually hobbyboards specialized sensors.
# These can only be read by OWFS.  Currently this driver only supports them
# via owserver (network protocol)

HOBBYBOARD_EF = {
    "HobbyBoards_EF": {
        "humidity": "humidity/humidity_corrected",
        "humidity_raw": "humidity/humidity_raw",
        "temperature": "humidity/temperature",
    },
    "HB_MOISTURE_METER": {
        "moisture_0": "moisture/sensor.0",
        "moisture_1": "moisture/sensor.1",
        "moisture_2": "moisture/sensor.2",
        "moisture_3": "moisture/sensor.3",
    },
}

SENSOR_TYPES = {
    # SensorType: [ Measured unit, Unit ]
    "temperature": ["temperature", TEMP_CELSIUS],
    "humidity": ["humidity", PERCENTAGE],
    "humidity_hih3600": ["humidity", PERCENTAGE],
    "humidity_hih4000": ["humidity", PERCENTAGE],
    "humidity_hih5030": ["humidity", PERCENTAGE],
    "humidity_htm1735": ["humidity", PERCENTAGE],
    "humidity_raw": ["humidity", PERCENTAGE],
    "pressure": ["pressure", "mb"],
    "illuminance": ["illuminance", LIGHT_LUX],
    "wetness_0": ["wetness", PERCENTAGE],
    "wetness_1": ["wetness", PERCENTAGE],
    "wetness_2": ["wetness", PERCENTAGE],
    "wetness_3": ["wetness", PERCENTAGE],
    "moisture_0": ["moisture", "cb"],
    "moisture_1": ["moisture", "cb"],
    "moisture_2": ["moisture", "cb"],
    "moisture_3": ["moisture", "cb"],
    "counter_a": ["counter", "count"],
    "counter_b": ["counter", "count"],
    "HobbyBoard": ["none", "none"],
    "voltage": ["voltage", VOLT],
    "voltage_VAD": ["voltage", VOLT],
    "voltage_VDD": ["voltage", VOLT],
    "current": ["current", ELECTRICAL_CURRENT_AMPERE],
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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the one wire Sensors."""
    base_dir = config[CONF_MOUNT_DIR]
    owport = config[CONF_PORT]
    owhost = config.get(CONF_HOST)
    if owhost:
        _LOGGER.debug("Initializing using %s:%s", owhost, owport)
    else:
        _LOGGER.debug("Initializing using %s", base_dir)

    devs = []
    device_names = {}
    if CONF_NAMES in config:
        if isinstance(config[CONF_NAMES], dict):
            device_names = config[CONF_NAMES]

    # We have an owserver on a remote(or local) host/port
    if owhost:
        try:
            owproxy = protocol.proxy(host=owhost, port=owport)
            devices = owproxy.dir()
        except protocol.Error as exc:
            _LOGGER.error(
                "Cannot connect to owserver on %s:%d, got: %s", owhost, owport, exc
            )
            devices = []
        for device in devices:
            _LOGGER.debug("Found device: %s", device)
            family = owproxy.read(f"{device}family").decode()
            dev_type = "std"
            if "EF" in family:
                dev_type = "HobbyBoard"
                family = owproxy.read(f"{device}type").decode()

            if family not in hb_info_from_type(dev_type):
                _LOGGER.warning(
                    "Ignoring unknown family (%s) of sensor found for device: %s",
                    family,
                    device,
                )
                continue
            for sensor_key, sensor_value in hb_info_from_type(dev_type)[family].items():
                if "moisture" in sensor_key:
                    s_id = sensor_key.split("_")[1]
                    is_leaf = int(
                        owproxy.read(f"{device}moisture/is_leaf.{s_id}").decode()
                    )
                    if is_leaf:
                        sensor_key = f"wetness_{s_id}"
                sensor_id = os.path.split(os.path.split(device)[0])[1]
                device_file = os.path.join(os.path.split(device)[0], sensor_value)
                devs.append(
                    OneWireProxy(
                        device_names.get(sensor_id, sensor_id),
                        device_file,
                        sensor_key,
                        owproxy,
                    )
                )

    # We have a raw GPIO ow sensor on a Pi
    elif base_dir == DEFAULT_SYSBUS_MOUNT_DIR:
        for device_family in DEVICE_SENSORS:
            for device_folder in glob(os.path.join(base_dir, f"{device_family}[.-]*")):
                sensor_id = os.path.split(device_folder)[1]
                device_file = os.path.join(device_folder, "w1_slave")
                devs.append(
                    OneWireDirect(
                        device_names.get(sensor_id, sensor_id),
                        device_file,
                        "temperature",
                    )
                )

    # We have an owfs mounted
    else:
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
                    devs.append(
                        OneWireOWFS(
                            device_names.get(sensor_id, sensor_id),
                            device_file,
                            sensor_key,
                        )
                    )

    if devs == []:
        _LOGGER.error(
            "No onewire sensor found. Check if dtoverlay=w1-gpio "
            "is in your /boot/config.txt. "
            "Check the mount_dir parameter if it's defined"
        )
        return

    add_entities(devs, True)


class OneWire(Entity):
    """Implementation of an One wire Sensor."""

    def __init__(self, name, device_file, sensor_type):
        """Initialize the sensor."""
        self._name = f"{name} {sensor_type.capitalize()}"
        self._device_file = device_file
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._state = None
        self._value_raw = None

    def _read_value_raw(self):
        """Read the value as it is returned by the sensor."""
        with open(self._device_file) as ds_device_file:
            lines = ds_device_file.readlines()
        return lines

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if "count" in self._unit_of_measurement:
            return int(self._state)
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {"device_file": self._device_file, "raw_value": self._value_raw}

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._device_file


class OneWireProxy(OneWire):
    """Implementation of a One wire Sensor through owserver."""

    def __init__(self, name, device_file, sensor_type, owproxy):
        """Initialize the onewire sensor via owserver."""
        super().__init__(name, device_file, sensor_type)
        self._owproxy = owproxy

    def _read_value_ownet(self):
        """Read a value from the owserver."""
        if self._owproxy:
            return self._owproxy.read(self._device_file).decode().lstrip()
        return None

    def update(self):
        """Get the latest data from the device."""
        value = None
        value_read = False
        try:
            value_read = self._read_value_ownet()
        except protocol.Error as exc:
            _LOGGER.error("Owserver failure in read(), got: %s", exc)
        if value_read:
            value = round(float(value_read), 1)
            self._value_raw = float(value_read)

        self._state = value


class OneWireDirect(OneWire):
    """Implementation of an One wire Sensor directly connected to RPI GPIO."""

    def update(self):
        """Get the latest data from the device."""
        value = None
        lines = self._read_value_raw()
        while lines[0].strip()[-3:] != "YES":
            time.sleep(0.2)
            lines = self._read_value_raw()
        equals_pos = lines[1].find("t=")
        if equals_pos != -1:
            value_string = lines[1][equals_pos + 2 :]
            value = round(float(value_string) / 1000.0, 1)
            self._value_raw = float(value_string)
        self._state = value


class OneWireOWFS(OneWire):
    """Implementation of an One wire Sensor through owfs."""

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
