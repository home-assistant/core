"""Netgear LTE sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.netgear_lte/
"""

import voluptuous as vol
import attr

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

from ..netgear_lte import DATA_KEY

DEPENDENCIES = ['netgear_lte']

CONF_SENSOR = 'sensor'
SENSOR_SMS = 'sms'
SENSOR_USAGE = 'usage'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSOR): vol.In([SENSOR_SMS, SENSOR_USAGE])
})


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info):
    """Set up Netgear LTE sensor devices."""
    lte_data = hass.data[DATA_KEY].get(config)

    if config[CONF_SENSOR] == SENSOR_SMS:
        async_add_devices([SMSSensor(lte_data)], True)
    elif config[CONF_SENSOR] == SENSOR_USAGE:
        async_add_devices([UsageSensor(lte_data)], True)


@attr.s
class LTESensor(Entity):
    """Data usage sensor entity."""

    lte_data = attr.ib()

    async def async_update(self):
        """Update state."""
        await self.lte_data.async_update()


class SMSSensor(LTESensor):
    """Unread SMS sensor entity."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Netgear LTE SMS"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.lte_data.unread_count


class UsageSensor(LTESensor):
    """Data usage sensor entity."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Netgear LTE usage"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.lte_data.usage
