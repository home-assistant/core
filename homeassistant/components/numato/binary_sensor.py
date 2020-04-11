"""
Binary sensor platform integration for Numato USB GPIO expanders.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/integrations/numato#binary-sensor
"""
import logging

from numato_gpio import NumatoGpioError
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorDevice
import homeassistant.components.numato as numato
from homeassistant.const import CONF_ID, DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_INVERT_LOGIC = "invert_logic"
CONF_PORTS = "ports"
CONF_DEVICES = "devices"
CONF_DEVICE_ID = "id"
DEFAULT_INVERT_LOGIC = False

DEPENDENCIES = ["numato"]

_PORTS_SCHEMA = vol.Schema({cv.positive_int: cv.string})
_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Required(CONF_PORTS): _PORTS_SCHEMA,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    }
)
_DEVICES_SCHEMA = vol.All(list, [_DEVICE_SCHEMA])
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_DEVICES): _DEVICES_SCHEMA})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the configured Numato USB GPIO binary sensor ports."""

    binary_sensors = []
    devices = config.get(CONF_DEVICES)
    for device in devices:
        device_id = device[CONF_ID]
        invert_logic = device[CONF_INVERT_LOGIC]
        ports = device[CONF_PORTS]
        for port_id, port_name in ports.items():
            try:
                binary_sensors.append(
                    NumatoGPIOBinarySensor(port_name, device_id, port_id, invert_logic)
                )
            except NumatoGpioError as ex:
                _LOGGER.error(
                    "Numato USB device %s port %s failed: %s",
                    device_id,
                    port_id,
                    str(ex),
                )
    add_devices(binary_sensors, True)


class NumatoGPIOBinarySensor(BinarySensorDevice):
    """Represents a binary sensor (input) port of a Numato GPIO expander."""

    def __init__(self, name, device_id, port, invert_logic):
        """Initialize the Numato GPIO based binary sensor."""
        # pylint: disable=no-member
        self._name = name or DEVICE_DEFAULT_NAME
        self._device_id = device_id
        self._port = port
        self._invert_logic = invert_logic
        self._state = None
        numato.setup_input(self._device_id, self._port)

        def read_gpio(port, level):
            self._state = level
            self.schedule_update_ha_state()

        numato.edge_detect(self._device_id, self._port, read_gpio)

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
        try:
            self._state = numato.read_input(self._device_id, self._port)
        except NumatoGpioError as err:
            self._state = None
            _LOGGER.error(
                "Failed to update Numato device %s port %s: %s",
                self._device_id,
                self._port,
                str(err),
            )
