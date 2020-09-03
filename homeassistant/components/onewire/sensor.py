"""Support for 1-Wire environment sensors."""
import os

from pyownet import protocol

from homeassistant.const import VOLT

from .const import CONF_TYPE_SYSBUS, LOGGER, SENSOR_TYPES
from .onewireentity import OneWireEntity
from .onewireproxy import OneWireProxy, get_proxy_from_config_entry

DEVICE_SENSORS = {
    # Family : { SensorType: owfs path }
    "10": {"temperature": "temperature"},
    "12": {"temperature": "TAI8570/temperature", "pressure": "TAI8570/pressure"},
    "22": {"temperature": "temperature"},
    "26": {
        "temperature": "temperature",
        "humidity": "humidity",
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


def hb_info_from_type(base_device_type="std"):
    """Return the proper info array for the device type."""
    if "HobbyBoard" in base_device_type:
        return HOBBYBOARD_EF
    return DEVICE_SENSORS


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Old way of setting up 1-Wire platform."""
    owproxy = OneWireProxy(hass, config)
    if not owproxy.setup():
        return False

    entities = get_entities(owproxy, config)
    add_entities(entities, True)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the 1-Wire sensors."""
    owproxy = get_proxy_from_config_entry(hass, config_entry)
    entities = get_entities(owproxy, config_entry.data)
    async_add_entities(entities, True)


def get_entities(owproxy, config):
    """Get a list of entities."""
    entities = []
    for device_id, device_path in owproxy.read_device_list().items():
        LOGGER.debug("Found device: %s", device_id)
        family = owproxy.read_family(device_path)
        device_type = owproxy.read_type(device_path)
        base_device_type = "std"
        if "EF" in family:
            base_device_type = "HobbyBoard"
            family = device_type
        LOGGER.info("Found device: %s (family: %s)", device_id, family)

        known_types = hb_info_from_type(base_device_type)
        if family not in known_types:
            LOGGER.debug(
                "Ignoring unknown sensor family (%s) for device: %s",
                family,
                device_id,
            )
            continue

        for sensor_key, sensor_value in known_types[family].items():
            if "moisture" in sensor_key:
                s_id = sensor_key.split("_")[1]
                is_leaf = int(
                    owproxy.read_value(f"{device_path}moisture/is_leaf.{s_id}")
                )
                if is_leaf:
                    sensor_key = f"wetness_{id}"
            device_file = os.path.join(os.path.split(device_path)[0], sensor_value)

            try:
                initial_value = owproxy.read_value(device_file)
                LOGGER.info("Adding 1-Wire sensor: %s", device_file)
                entities.append(
                    OneWireSensor(
                        device_id,
                        device_file,
                        device_type,
                        sensor_key,
                        owproxy,
                        initial_value,
                    )
                )
            except protocol.Error as exc:
                LOGGER.error("Owserver failure in read(), got: %s", exc)

    if entities == []:
        LOGGER.warning(
            "No 1-Wire sensor found. Check if dtoverlay=w1-gpio "
            "is in your /boot/config.txt. "
            "Check the mount_dir parameter if it's defined"
        )
    return entities


class OneWireSensor(OneWireEntity):
    """Implementation of a 1-Wire sensor."""

    def __init__(
        self, name, device_file, device_type, sensor_type, proxy, initial_value
    ):
        """Initialize the sensor."""
        super().__init__(
            name, device_file, device_type, sensor_type, proxy, initial_value
        )
        self._unit_of_measurement = None
        if SENSOR_TYPES.get(sensor_type) is not None:
            self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        if initial_value:
            self._state = self.get_state_value(initial_value)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from the device."""
        try:
            value_read = self.read_value()
            self._value_raw = value_read
            self._state = self.get_state_value(value_read)
        except protocol.Error as exc:
            LOGGER.error("Owserver failure in read(), got: %s", exc)
            self._state = None

    def get_state_value(self, raw_value):
        """Compute state value based on raw_value."""
        if self._proxy.conf_type == CONF_TYPE_SYSBUS:
            raw_value = float(raw_value) / 1000.0
        if self._unit_of_measurement is not None:
            if self._unit_of_measurement == VOLT:
                return round(float(raw_value), 2)
            if "count" in self._unit_of_measurement:
                return int(raw_value)
        return round(float(raw_value), 1)
