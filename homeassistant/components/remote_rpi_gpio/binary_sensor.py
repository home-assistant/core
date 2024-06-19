"""Support for binary sensor using RPi GPIO."""

from __future__ import annotations

import requests
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .. import remote_rpi_gpio
from . import (
    CONF_BOUNCETIME,
    CONF_INVERT_LOGIC,
    CONF_PULL_MODE,
    DEFAULT_BOUNCETIME,
    DEFAULT_INVERT_LOGIC,
    DEFAULT_PULL_MODE,
)

CONF_PORTS = "ports"

_SENSORS_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORTS): _SENSORS_SCHEMA,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
        vol.Optional(CONF_BOUNCETIME, default=DEFAULT_BOUNCETIME): cv.positive_int,
        vol.Optional(CONF_PULL_MODE, default=DEFAULT_PULL_MODE): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Raspberry PI GPIO devices."""
    address = config["host"]
    invert_logic = config[CONF_INVERT_LOGIC]
    pull_mode = config[CONF_PULL_MODE]
    ports = config["ports"]
    bouncetime = config[CONF_BOUNCETIME] / 1000

    devices = []
    for port_num, port_name in ports.items():
        try:
            remote_sensor = remote_rpi_gpio.setup_input(
                address, port_num, pull_mode, bouncetime
            )
        except (ValueError, IndexError, KeyError, OSError):
            return
        new_sensor = RemoteRPiGPIOBinarySensor(port_name, remote_sensor, invert_logic)
        devices.append(new_sensor)

    add_entities(devices, True)


class RemoteRPiGPIOBinarySensor(BinarySensorEntity):
    """Represent a binary sensor that uses a Remote Raspberry Pi GPIO."""

    _attr_should_poll = False

    def __init__(self, name, sensor, invert_logic):
        """Initialize the RPi binary sensor."""
        self._name = name
        self._invert_logic = invert_logic
        self._state = False
        self._sensor = sensor

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        def read_gpio():
            """Read state from GPIO."""
            self._state = remote_rpi_gpio.read_input(self._sensor)
            self.schedule_update_ha_state()

        self._sensor.when_deactivated = read_gpio
        self._sensor.when_activated = read_gpio

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state != self._invert_logic

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return

    def update(self) -> None:
        """Update the GPIO state."""
        try:
            self._state = remote_rpi_gpio.read_input(self._sensor)
        except requests.exceptions.ConnectionError:
            return
