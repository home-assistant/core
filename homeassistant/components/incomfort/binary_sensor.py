"""Support for an Intergas boiler via an InComfort/InTouch Lan2RF gateway."""
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up an InComfort/InTouch binary_sensor device."""
    client = hass.data[DOMAIN]['client']
    heater = hass.data[DOMAIN]['heater']

    async_add_entities([
        IncomfortBurning(client, heater),
        IncomfortPumping(client, heater),
        IncomfortTapping(client, heater),
        IncomfortFailed(client, heater)
    ])


class IncomfortBinarySensor(BinarySensorDevice):
    """Representation of an InComfort/InTouch binary_sensor device."""

    def __init__(self, client, boiler):
        """Initialize the binary sensor."""
        self._client = client
        self._boiler = boiler

        self._name = None
        self._is_on_key = None
        self._other_key = None

    async def async_added_to_hass(self):
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._connect)

    @callback
    def _connect(self, packet):
        if packet['signal'] == 'refresh':
            self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._boiler.status[self._is_on_key]

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self._other_key is None:
            return None
        value = self._boiler.status[self._other_key] if self.is_on else None
        return {self._other_key: value}

    @property
    def should_poll(self) -> bool:
        """Return False as this device should never be polled."""
        return False


class IncomfortBurning(IncomfortBinarySensor):
    """Representation of an InComfort Burning sensor."""

    def __init__(self, client, boiler):
        """Initialize the binary sensor."""
        super().__init__(client, boiler)

        self._name = 'Burning'
        self._is_on_key = 'is_burning'


class IncomfortFailed(IncomfortBinarySensor):
    """Representation of an InComfort Failed sensor."""

    def __init__(self, client, boiler):
        """Initialize the binary sensor."""
        super().__init__(client, boiler)

        self._name = 'Failed'
        self._is_on_key = 'is_failed'
        self._other_key = 'fault_code'


class IncomfortPumping(IncomfortBinarySensor):
    """Representation of an InComfort Pumping sensor."""

    def __init__(self, client, boiler):
        """Initialize the binary sensor."""
        super().__init__(client, boiler)

        self._name = 'Pumping'
        self._is_on_key = 'is_pumping'
        self._other_key = 'heater_temp'


class IncomfortTapping(IncomfortBinarySensor):
    """Representation of an InComfort Tapping sensor."""

    def __init__(self, client, boiler):
        """Initialize the binary sensor."""
        super().__init__(client, boiler)

        self._name = 'Tapping'
        self._is_on_key = 'is_tapping'
        self._other_key = 'tap_temp'
