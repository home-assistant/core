"""Binary sensor platform integration for Numato USB GPIO expanders."""
import logging

from numato_gpio import NumatoGpioError

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import DEVICE_DEFAULT_NAME

from . import (
    CONF_BINARY_SENSORS,
    CONF_DEVICES,
    CONF_ID,
    CONF_INVERT_LOGIC,
    CONF_PORTS,
    DATA_API,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the configured Numato USB GPIO binary sensor ports."""
    if discovery_info is None:
        return
    binary_sensors = []
    devices = hass.data[DOMAIN][CONF_DEVICES]
    for device in [d for d in devices if CONF_BINARY_SENSORS in d]:
        device_id = device[CONF_ID]
        platform = device[CONF_BINARY_SENSORS]
        invert_logic = platform[CONF_INVERT_LOGIC]
        ports = platform[CONF_PORTS]
        for port, port_name in ports.items():
            binary_sensors.append(
                NumatoGPIOBinarySensor(
                    port_name,
                    device_id,
                    port,
                    invert_logic,
                    hass.data[DOMAIN][DATA_API],
                )
            )
    add_entities(binary_sensors, True)


class NumatoGPIOBinarySensor(BinarySensorDevice):
    """Represents a binary sensor (input) port of a Numato GPIO expander."""

    def __init__(self, name, device_id, port, invert_logic, api):
        """Initialize the Numato GPIO based binary sensor object."""
        # pylint: disable=no-member
        self._name = name or DEVICE_DEFAULT_NAME
        self._device_id = device_id
        self._port = port
        self._invert_logic = invert_logic
        self._state = None
        self._api = api

    async def async_added_to_hass(self):
        """Configure the device port as a binary sensor with edge detection."""
        try:
            await self.hass.async_add_executor_job(
                self._api.setup_input, self._device_id, self._port
            )

            def read_gpio(port, level):
                self._state = level
                self.schedule_update_ha_state()

            await self.hass.async_add_executor_job(
                self._api.edge_detect, self._device_id, self._port, read_gpio
            )
        except NumatoGpioError as err:
            _LOGGER.error(
                "Numato USB device %s port %s failed: %s",
                self._device_id,
                self._port,
                str(err),
            )

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
            self._state = self._api.read_input(self._device_id, self._port)
        except NumatoGpioError as err:
            self._state = None
            _LOGGER.error(
                "Failed to update Numato device %s port %s: %s",
                self._device_id,
                self._port,
                str(err),
            )
