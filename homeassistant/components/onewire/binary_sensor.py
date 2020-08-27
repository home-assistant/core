"""Support for 1-Wire environment binary sensors."""
import os

from pyownet import protocol

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import CONF_NAMES, LOGGER
from .onewireentity import OneWireEntity
from .onewireproxy import OneWireProxy, get_proxy_from_config_entry

DEVICE_BINARY_SENSORS = {
    # Family : { SensorType: owfs path }
    "12": {"sensed_a": "sensed.A", "sensed_b": "sensed.B"},
    "29": {
        "sensed_0": "sensed.0",
        "sensed_1": "sensed.1",
        "sensed_2": "sensed.2",
        "sensed_3": "sensed.3",
        "sensed_4": "sensed.4",
        "sensed_5": "sensed.5",
        "sensed_6": "sensed.6",
        "sensed_7": "sensed.7",
    },
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Old way of setting up deCONZ platforms."""
    owproxy = OneWireProxy(hass, config)
    if not owproxy.setup():
        return False

    entities = get_entities(owproxy, config)
    add_entities(entities, True)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the one wire Sensors."""
    owproxy = get_proxy_from_config_entry(hass, config_entry)
    entities = get_entities(owproxy, config_entry.data)
    async_add_entities(entities, True)


def get_entities(owproxy, config):
    """Get a list of entities."""
    entities = []
    device_names = {}
    if CONF_NAMES in config:
        if isinstance(config[CONF_NAMES], dict):
            device_names = config[CONF_NAMES]

    for device in owproxy.read_device_list():
        LOGGER.debug("Found device: %s", device)
        family = owproxy.read_family(device)
        if family not in DEVICE_BINARY_SENSORS:
            LOGGER.debug(
                "Ignoring unknown family (%s) of binary sensor found for device: %s",
                family,
                device,
            )
            continue

        for sensor_key, sensor_value in DEVICE_BINARY_SENSORS[family].items():
            sensor_id = os.path.split(os.path.split(device)[0])[1]
            device_file = os.path.join(os.path.split(device)[0], sensor_value)

            try:
                initial_value = owproxy.read_value(device_file)
                LOGGER.info("Adding one-wire binary sensor: %s", device_file)
                entities.append(
                    OneWireBinarySensor(
                        device_names.get(sensor_id, sensor_id),
                        device_file,
                        sensor_key,
                        owproxy,
                        initial_value,
                    )
                )
            except protocol.Error as exc:
                LOGGER.error("Owserver failure in read(), got: %s", exc)

    if entities == []:
        LOGGER.error(
            "No onewire sensor found. Check if dtoverlay=w1-gpio "
            "is in your /boot/config.txt. "
            "Check the mount_dir parameter if it's defined"
        )

    return entities


class OneWireBinarySensor(OneWireEntity, BinarySensorEntity):
    """Implementation of a One wire Sensor."""

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    def update(self):
        """Get the latest data from the device."""
        value = None
        value_read = False
        try:
            value_read = self.read_value()
        except protocol.Error as exc:
            LOGGER.error("Owserver failure in read(), got: %s", exc)
        if value_read:
            value = int(value_read) == 1
            self._value_raw = value_read

        self._state = value
