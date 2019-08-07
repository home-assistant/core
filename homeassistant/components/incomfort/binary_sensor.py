"""Support for an Intergas boiler via an InComfort/InTouch Lan2RF gateway."""
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up an InComfort/InTouch binary_sensor device."""
    async_add_entities(
        [IncomfortFailed(hass.data[DOMAIN]["client"], hass.data[DOMAIN]["heater"])]
    )


class IncomfortFailed(BinarySensorDevice):
    """Representation of an InComfort Failed sensor."""

    def __init__(self, client, boiler):
        """Initialize the binary sensor."""
        self._client = client
        self._boiler = boiler

    async def async_added_to_hass(self):
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @callback
    def _refresh(self):
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Fault state"

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._boiler.status["is_failed"]

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {"fault_code": self._boiler.status["fault_code"]}

    @property
    def should_poll(self) -> bool:
        """Return False as this device should never be polled."""
        return False
