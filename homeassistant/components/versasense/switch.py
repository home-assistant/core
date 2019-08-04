"""Support for VersaSense actuator peripheral."""
import logging

from homeassistant.components.switch import SwitchDevice

from . import DOMAIN
from .const import PERIPHERAL_STATE_ON, PERIPHERAL_STATE_OFF

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
):
    """Set up actuator platform."""
    consumer = hass.data[DOMAIN]["consumer"]
    peripheral = hass.data[DOMAIN][discovery_info["identifier"]]
    parent_name = discovery_info["parent_name"]
    unit = discovery_info["unit"]
    measurement = discovery_info["measurement"]

    async_add_entities(
        [VActuator(peripheral, parent_name, unit, measurement, consumer)]
    )


class VActuator(SwitchDevice):
    """Representation of an Actuator."""

    def __init__(self, peripheral, parent_name, unit, measurement, consumer):
        """Initialize the sensor."""
        self._is_on = False
        self._name = "{} {}".format(parent_name, measurement)
        self._parent_mac = peripheral.parentMac
        self._identifier = peripheral.identifier
        self._unit = unit
        self._measurement = measurement
        self.consumer = consumer

    @property
    def unique_id(self):
        """Return the unique id of the actuator."""
        return "{}/{}/{}".format(
            self._parent_mac,
            self._identifier,
            self._measurement
        )

    @property
    def name(self):
        """Return the name of the actuator."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the actuator."""
        return self._is_on

    async def async_turn_off(self, **kwargs):
        """Turn off the actuator."""
        await self.update_state(0)

    async def async_turn_on(self, **kwargs):
        """Turn on the actuator."""
        await self.update_state(1)

    async def update_state(self, state):
        """Update the state of the actuator."""
        payload = {"id": "state-num", "value": state}

        await self.consumer.actuatePeripheral(
            None, self._identifier, self._parent_mac, payload
        )

    async def async_update(self):
        """Fetch state data from the actuator."""
        samples = await self.consumer.fetchPeripheralSample(
            None, self._identifier, self._parent_mac
        )

        if samples is not None:
            for sample in samples:
                if sample.measurement == self._measurement:
                    if sample.value == PERIPHERAL_STATE_OFF:
                        self._is_on = False
                    elif sample.value == PERIPHERAL_STATE_ON:
                        self._is_on = True
        else:
            _LOGGER.error("Sample unavailable")
            self._is_on = None
