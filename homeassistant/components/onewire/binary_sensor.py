"""Support for 1-Wire environment binary sensors."""
import os

from pyownet import protocol

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import LOGGER
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
    """Old way of setting up 1-Wire platform."""
    owproxy = OneWireProxy(hass, config)
    if not owproxy.setup():
        return False

    entities = get_entities(owproxy, config)
    add_entities(entities, True)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the 1-Wire binary sensors."""
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
        if family not in DEVICE_BINARY_SENSORS:
            LOGGER.debug(
                "Ignoring unknown binary sensor family (%s) for device: %s",
                family,
                device_id,
            )
            continue

        for sensor_key, sensor_value in DEVICE_BINARY_SENSORS[family].items():
            device_file = os.path.join(os.path.split(device_path)[0], sensor_value)

            try:
                initial_value = owproxy.read_value(device_file)
                LOGGER.info("Adding 1-Wire binary sensor: %s", device_file)
                entities.append(
                    OneWireBinarySensor(
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

    return entities


class OneWireBinarySensor(OneWireEntity, BinarySensorEntity):
    """Implementation of a 1-Wire binary sensor."""

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
