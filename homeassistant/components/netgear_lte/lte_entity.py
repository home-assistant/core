"""Support for Netgear LTE entity base class."""
import attr

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import DISPATCHER_NETGEAR_LTE


@attr.s
class LTEEntity(Entity):
    """Base LTE entity."""

    modem_data = attr.ib()
    sensor_type = attr.ib()

    _unique_id = attr.ib(init=False)

    @_unique_id.default
    def _init_unique_id(self):
        """Register unique_id while we know data is valid."""
        return "{}_{}".format(
            self.sensor_type, self.modem_data.data.serial_number)

    async def async_added_to_hass(self):
        """Register callback."""
        async_dispatcher_connect(
            self.hass, DISPATCHER_NETGEAR_LTE, self.async_write_ha_state)

    async def async_update(self):
        """Force update of state."""
        await self.modem_data.async_update()

    @property
    def should_poll(self):
        """Return that the sensor should not be polled."""
        return False

    @property
    def available(self):
        """Return the availability of the sensor."""
        return self.modem_data.data is not None

    @property
    def unique_id(self):
        """Return a unique ID like 'usage_5TG365AB0078V'."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Netgear LTE {}".format(self.sensor_type)
