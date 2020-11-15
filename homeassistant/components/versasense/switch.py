"""Support for VersaSense actuator peripheral."""
import logging

from homeassistant.components.switch import SwitchEntity

from . import DOMAIN
from .const import (
    KEY_CONSUMER,
    KEY_IDENTIFIER,
    KEY_MEASUREMENT,
    KEY_PARENT_MAC,
    KEY_PARENT_NAME,
    KEY_UNIT,
    PERIPHERAL_STATE_OFF,
    PERIPHERAL_STATE_ON,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up actuator platform."""
    if discovery_info is None:
        return None

    consumer = hass.data[DOMAIN][KEY_CONSUMER]

    actuator_list = []

    for entity_info in discovery_info:
        peripheral = hass.data[DOMAIN][entity_info[KEY_PARENT_MAC]][
            entity_info[KEY_IDENTIFIER]
        ]
        parent_name = entity_info[KEY_PARENT_NAME]
        unit = entity_info[KEY_UNIT]
        measurement = entity_info[KEY_MEASUREMENT]

        actuator_list.append(
            VActuator(peripheral, parent_name, unit, measurement, consumer)
        )

    async_add_entities(actuator_list)


class VActuator(SwitchEntity):
    """Representation of an Actuator."""

    def __init__(self, peripheral, parent_name, unit, measurement, consumer):
        """Initialize the sensor."""
        self._is_on = False
        self._available = True
        self._name = f"{parent_name} {measurement}"
        self._parent_mac = peripheral.parentMac
        self._identifier = peripheral.identifier
        self._unit = unit
        self._measurement = measurement
        self.consumer = consumer

    @property
    def unique_id(self):
        """Return the unique id of the actuator."""
        return f"{self._parent_mac}/{self._identifier}/{self._measurement}"

    @property
    def name(self):
        """Return the name of the actuator."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the actuator."""
        return self._is_on

    @property
    def available(self):
        """Return if the actuator is available."""
        return self._available

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
                    self._available = True
                    if sample.value == PERIPHERAL_STATE_OFF:
                        self._is_on = False
                    elif sample.value == PERIPHERAL_STATE_ON:
                        self._is_on = True
                    break
        else:
            _LOGGER.error("Sample unavailable")
            self._available = False
            self._is_on = None
