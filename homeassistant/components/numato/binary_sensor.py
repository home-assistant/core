"""Binary sensor platform integration for Numato USB GPIO expanders."""
from functools import partial
import logging

from numato_gpio import NumatoGpioError

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send

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

NUMATO_SIGNAL = "numato_signal_{}_{}"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the configured Numato USB GPIO binary sensor ports."""
    if discovery_info is None:
        return

    def read_gpio(device_id, port, level):
        """Send signal to entity to have it update state."""
        dispatcher_send(hass, NUMATO_SIGNAL.format(device_id, port), level)

    api = hass.data[DOMAIN][DATA_API]
    binary_sensors = []
    devices = hass.data[DOMAIN][CONF_DEVICES]
    for device in [d for d in devices if CONF_BINARY_SENSORS in d]:
        device_id = device[CONF_ID]
        platform = device[CONF_BINARY_SENSORS]
        invert_logic = platform[CONF_INVERT_LOGIC]
        ports = platform[CONF_PORTS]
        for port, port_name in ports.items():
            try:

                api.setup_input(device_id, port)
                api.edge_detect(device_id, port, partial(read_gpio, device_id))

            except NumatoGpioError as err:
                _LOGGER.error(
                    "Failed to initialize binary sensor '%s' on Numato device %s port %s: %s",
                    port_name,
                    device_id,
                    port,
                    err,
                )
                continue

            binary_sensors.append(
                NumatoGpioBinarySensor(port_name, device_id, port, invert_logic, api,)
            )
    add_entities(binary_sensors, True)


class NumatoGpioBinarySensor(BinarySensorDevice):
    """Represents a binary sensor (input) port of a Numato GPIO expander."""

    def __init__(self, name, device_id, port, invert_logic, api):
        """Initialize the Numato GPIO based binary sensor object."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._device_id = device_id
        self._port = port
        self._invert_logic = invert_logic
        self._state = None
        self._api = api

    async def async_added_to_hass(self):
        """Connect state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                NUMATO_SIGNAL.format(self._device_id, self._port),
                self._async_update_state,
            )
        )

    @callback
    def _async_update_state(self, level):
        """Update entity state."""
        self._state = level
        self.async_write_ha_state()

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
                err,
            )
