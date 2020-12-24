"""Support for binary sensor using Orange Pi GPIO."""

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity

from . import edge_detect, read_input, setup_input, setup_mode
from .const import CONF_INVERT_LOGIC, CONF_PIN_MODE, CONF_PORTS, PORT_SCHEMA

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(PORT_SCHEMA)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Orange Pi GPIO platform."""
    binary_sensors = []
    invert_logic = config[CONF_INVERT_LOGIC]
    pin_mode = config[CONF_PIN_MODE]
    ports = config[CONF_PORTS]

    setup_mode(pin_mode)

    for port_num, port_name in ports.items():
        binary_sensors.append(
            OPiGPIOBinarySensor(hass, port_name, port_num, invert_logic)
        )
    async_add_entities(binary_sensors)


class OPiGPIOBinarySensor(BinarySensorEntity):
    """Represent a binary sensor that uses Orange Pi GPIO."""

    def __init__(self, hass, name, port, invert_logic):
        """Initialize the Orange Pi binary sensor."""
        self._name = name
        self._port = port
        self._invert_logic = invert_logic
        self._state = None

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""

        def gpio_edge_listener(port):
            """Update GPIO when edge change is detected."""
            self.schedule_update_ha_state(True)

        def setup_entity():
            setup_input(self._port)
            edge_detect(self._port, gpio_edge_listener)
            self.schedule_update_ha_state(True)

        await self.hass.async_add_executor_job(setup_entity)

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
        """Update state with new GPIO data."""
        self._state = read_input(self._port)
