"""Support for binary sensor using RPi GPIO."""

from homeassistant.components import rpi_gpio
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.rpi_gpio.const import (
    CONF_SENSOR,
    CONF_SENSOR_BOUNCETIME,
    CONF_SENSOR_INVERT_LOGIC,
    CONF_SENSOR_PORTS,
    CONF_SENSOR_PULL_MODE,
    DOMAIN,
    PLATFORMS,
)
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.reload import setup_reload_service


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Raspberry PI GPIO devices."""

    setup_reload_service(hass, DOMAIN, PLATFORMS)
    config_sensor = hass.data[DOMAIN][CONF_SENSOR]
    pull_mode = config_sensor[CONF_SENSOR_PULL_MODE]
    bouncetime = config_sensor[CONF_SENSOR_BOUNCETIME]
    invert_logic = config_sensor[CONF_SENSOR_INVERT_LOGIC]

    binary_sensors = []
    ports = config_sensor[CONF_SENSOR_PORTS]
    for port_num, port_name in ports.items():
        binary_sensors.append(
            RPiGPIOBinarySensor(
                port_name, port_num, pull_mode, bouncetime, invert_logic
            )
        )
    add_entities(binary_sensors, True)


class RPiGPIOBinarySensor(BinarySensorEntity):
    """Represent a binary sensor that uses Raspberry Pi GPIO."""

    def __init__(self, name, port, pull_mode, bouncetime, invert_logic):
        """Initialize the RPi binary sensor."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._port = port
        self._pull_mode = pull_mode
        self._bouncetime = bouncetime
        self._invert_logic = invert_logic
        self._state = None

        rpi_gpio.setup_input(self._port, self._pull_mode)

        def read_gpio(port):
            """Read state from GPIO."""
            self._state = rpi_gpio.read_input(self._port)
            self.schedule_update_ha_state()

        rpi_gpio.edge_detect(self._port, read_gpio, self._bouncetime)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state != self._invert_logic

    def update(self):
        """Update the GPIO state."""
        self._state = rpi_gpio.read_input(self._port)
