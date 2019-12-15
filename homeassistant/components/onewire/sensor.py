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
    STATE_OFF,
    STATE_OK,
    STATE_ON,
    STATE_PROBLEM,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_MOUNT_DIR = "mount_dir"
CONF_NAMES = "names"

DEFAULT_MOUNT_DIR = "/sys/bus/w1/devices/"
DEVICE_SENSORS = {
    "10": {"temperature": "temperature"},
    "12": {"temperature": "TAI8570/temperature", "pressure": "TAI8570/pressure"},
    "22": {"temperature": "temperature"},
    "26": {
        "temperature": "temperature",
        "humidity": "humidity",
        "pressure": "B1-R1-A/pressure",
        "illuminance": "S3-R1-A/illuminance",
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
    "HB_HUB": {
        "branch_0": "hub/branch.0",
        "branch_1": "hub/branch.1",
        "branch_2": "hub/branch.2",
        "branch_3": "hub/branch.3",
        "short_0": "hub/short.0",
        "short_1": "hub/short.1",
        "short_2": "hub/short.2",
        "short_3": "hub/short.3",
    },
}

SENSOR_TYPES = {
    "temperature": ["temperature", TEMP_CELSIUS],
    "humidity": ["humidity", "%"],
    "humidity_raw": ["humidity", "%"],
    "pressure": ["pressure", "mb"],
    "illuminance": ["illuminance", "lux"],
    "wetness_0": ["wetness", "%"],
    "wetness_1": ["wetness", "%"],
    "wetness_2": ["wetness", "%"],
    "wetness_3": ["wetness", "%"],
    "moisture_0": ["moisture", "cb"],
    "moisture_1": ["moisture", "cb"],
    "moisture_2": ["moisture", "cb"],
    "moisture_3": ["moisture", "cb"],
    "counter_a": ["counter", "count"],
    "counter_b": ["counter", "count"],
    "HobbyBoard": ["none", "none"],
    "branch_0": ["presense", "present"],
    "branch_1": ["presense", "present"],
    "branch_2": ["presense", "present"],
    "branch_3": ["presense", "present"],
    "short_0": ["problem", "short"],
    "short_1": ["problem", "short"],
    "short_2": ["problem", "short"],
    "short_3": ["problem", "short"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAMES): {cv.string: cv.string},
        vol.Optional(CONF_MOUNT_DIR, default=DEFAULT_MOUNT_DIR): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=4304): cv.port,
    }
)


def hb_info_from_type(type="std"):
    """Return the proper info array for the device type."""
    if "std" in type:
        return DEVICE_SENSORS
    if "HobbyBoard" in type:
        return HOBBYBOARD_EF


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the one wire Sensors."""
    base_dir = config.get(CONF_MOUNT_DIR)
    owport = config.get(CONF_PORT)
    owhost = config.get(CONF_HOST)
    devs = []
    device_names = {}
    if "names" in config:
        if isinstance(config["names"], dict):
            device_names = config["names"]

    # We have an owserver on a remote(or local) host/port
    if owhost:
        try:
            owproxy = protocol.proxy(host=owhost, port=owport)
            devices = owproxy.dir()
        except protocol.Error as exc:
            _LOGGER.error(f"Cannot connect to owserver on {owhost}:{owport}, got:{exc}")
        for device in devices:
            _LOGGER.debug(f"found device={device}")
            family = bytes.decode(owproxy.read(device + "family"))
            type = "std"
            if "EF" in family:
                type = "HobbyBoard"
                family = bytes.decode(owproxy.read(device + "type"))

            if family in hb_info_from_type(type):
                for sensor_key, sensor_value in hb_info_from_type(type)[family].items():
                    if "moisture" in sensor_key:
                        id = sensor_key.split("_")[1]
                        is_leaf = int(
                            bytes.decode(
                                owproxy.read(device + "moisture/is_leaf." + id)
                            )
                        )
                        if is_leaf:
                            sensor_key = "wetness_" + id
                    sensor_id = os.path.split(os.path.split(device)[0])[1]
                    device_file = os.path.join(os.path.split(device)[0], sensor_value)
                    devs.append(
                        OneWireProxy(
                            device_names.get(sensor_id, sensor_id),
                            device_file,
                            sensor_key,
                            owproxy=owproxy,
                        )
                    )
            else:
                _LOGGER.warning(
                    f"Ignoring unknown family ({family}) of sensor found for device: {device}"
                )

    # We have a raw GPIO ow sensor on a Pi
    elif base_dir == DEFAULT_MOUNT_DIR:
        for device_family in DEVICE_SENSORS:
            for device_folder in glob(os.path.join(base_dir, device_family + "[.-]*")):
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
            with open(family_file_path, "r") as family_file:
                family = family_file.read()
            if "EF" in family:
                next
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

    def __init__(self, name, device_file, sensor_type, owproxy=None):
        """Initialize the sensor."""
        self._name = name + " " + sensor_type.capitalize()
        self._device_file = device_file
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._state = None
        self._owproxy = owproxy

    def _read_value_raw(self):
        """Read the value as it is returned by the sensor."""
        with open(self._device_file, "r") as ds_device_file:
            lines = ds_device_file.readlines()
        return lines

    def _read_value_ownet(self):
        """Read a value from the owserver."""
        if self._owproxy:
            return bytes.decode(self._owproxy.read(self._device_file)).lstrip()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if "count" in self._unit_of_measurement:
            return int(self._state)
        if "short" in self._unit_of_measurement:
            return STATE_PROBLEM if int(self._state) else STATE_OK
        if "present" in self._unit_of_measurement:
            return STATE_ON if int(self._state) else STATE_OFF
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement


class OneWireProxy(OneWire):
    """Implementation of a One wire Sensor through owserver."""

    def update(self):
        """Get the latest data from the device."""
        value = None
        try:
            value_read = self._read_value_ownet()
            if len(value_read) > 0:
                value = round(float(value_read), 1)
        except protocol.Error as exc:
            _LOGGER.error(f"Owserver failure in read(), got:{exc}")

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
        except ValueError:
            _LOGGER.warning(f"Invalid value read from {self._device_file}")
        except FileNotFoundError:
            _LOGGER.warning(f"Cannot read from sensor: {self._device_file}")

        self._state = value
