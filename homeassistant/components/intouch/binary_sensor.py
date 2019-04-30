"""Support for the Sensors of an Intouch Lan2RF gateway."""
import asyncio
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up an Intouch sensor entity."""
    client = hass.data[DOMAIN]['client']

    water_heaters = await client.heaters
    await water_heaters[0].update()

    async_add_entities([
        IntouchBurning(client, water_heaters[0]),
        IntouchPumping(client, water_heaters[0]),
        IntouchTapping(client, water_heaters[0]),
        IntouchFailed(client, water_heaters[0])
    ])


class IntouchBinarySensor(BinarySensorDevice):
    """Representation of an InTouch binary sensor."""

    async def async_added_to_hass(self):
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._connect)

    @callback
    def _connect(self, packet):
        if packet['signal'] == 'refresh':
            self.async_schedule_update_ha_state(force_refresh=True)

    def __init__(self, client, boiler):
        """Initialize the binary sensor."""
        self._client = client
        self._objref = boiler

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._is_on

    @property
    def should_poll(self) -> bool:
        """Return True as this device should never be polled."""
        return False

    async def async_update(self):
        """Get the latest data from the hub."""
        try:
            await self._objref.update()

        except (AssertionError, asyncio.TimeoutError) as err:
            _LOGGER.warning("Update for %s failed, message: %s",
                            self._id, err)


class IntouchBurning(IntouchBinarySensor):
    """Representation of an InTouch Burning sensor."""

    def __init__(self, client, boiler):
        """Initialize the binary sensor."""
        super().__init__(client, boiler)

        self._name = 'Burning'
        self._is_on = self._objref.is_burning


class IntouchFailed(IntouchBinarySensor):
    """Representation of an InTouch Failed sensor."""

    def __init__(self, client, boiler):
        """Initialize the binary sensor."""
        super().__init__(client, boiler)

        self._name = 'Failed'
        self._is_on = self._objref.is_failed


class IntouchPumping(IntouchBinarySensor):
    """Representation of an InTouch Pumping sensor."""

    def __init__(self, client, boiler):
        """Initialize the binary sensor."""
        super().__init__(client, boiler)

        self._name = 'Pumping'
        self._is_on = self._objref.is_pumping


class IntouchTapping(IntouchBinarySensor):
    """Representation of an InTouch Tapping sensor."""

    def __init__(self, client, boiler):
        """Initialize the binary sensor."""
        super().__init__(client, boiler)

        self._name = 'Tapping'
        self._is_on = self._objref.is_tapping
