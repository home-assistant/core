"""Support for 1-Wire environment binary sensors."""
import os

from pyownet import protocol

from homeassistant.components.switch import SwitchEntity

from .onewireproxy import get_proxy_from_config_entry, OneWireProxy
from .onewireentity import OneWireEntity
from .const import (
    CONF_NAMES,
    LOGGER,
)


DEVICE_SWITCH = {
    # Family : { SensorType: owfs path }
    "12": {
        "pio_a": "PIO.A",
        "pio_b": "PIO.B",
        "latch_a": "latch.A",
        "latch_b": "latch.B",
    },
    "29": {
        "pio_0": "PIO.0",
        "pio_1": "PIO.1",
        "pio_2": "PIO.2",
        "pio_3": "PIO.3",
        "pio_4": "PIO.4",
        "pio_5": "PIO.5",
        "pio_6": "PIO.6",
        "pio_7": "PIO.7",
        "latch_0": "latch.0",
        "latch_1": "latch.1",
        "latch_2": "latch.2",
        "latch_3": "latch.3",
        "latch_4": "latch.4",
        "latch_5": "latch.5",
        "latch_6": "latch.6",
        "latch_7": "latch.7",
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
        if family not in DEVICE_SWITCH:
            LOGGER.debug(
                "Ignoring unknown family (%s) of switch found for device: %s",
                family,
                device,
            )
            continue

        for sensor_key, sensor_value in DEVICE_SWITCH[family].items():
            sensor_id = os.path.split(os.path.split(device)[0])[1]
            device_file = os.path.join(os.path.split(device)[0], sensor_value)

            try:
                initial_value = owproxy.read_value(device_file)
                LOGGER.info("Adding one-wire switch: %s", device_file)
                entities.append(
                    OneWireSwitchSensor(
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


class OneWireSwitchSensor(OneWireEntity, SwitchEntity):
    """Implementation of a One wire Sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return self._state

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        try:
            self.write_value(b"1")
        except protocol.Error as exc:
            LOGGER.error("Owserver failure in read(), got: %s", exc)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity on."""
        try:
            self.write_value(b"0")
        except protocol.Error as exc:
            LOGGER.error("Owserver failure in read(), got: %s", exc)

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

