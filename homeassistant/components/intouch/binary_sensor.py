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
        """Return True as this device should always be polled."""
        return True

    async def async_update(self):
        """Get the latest state data from the gateway."""
        try:
            await self._objref.update()

        except (AssertionError, asyncio.TimeoutError) as err:
            _LOGGER.warning("Update for %s failed, message: %s",
                            self._name, err)

        # inform the child devices that updated state data is available
        async_dispatcher_send(self.hass, DOMAIN, {'signal': 'refresh'})


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
