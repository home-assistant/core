"""Netgear LTE sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.netgear_lte/
"""

import voluptuous as vol
import attr

from homeassistant.const import CONF_HOST, CONF_SENSORS
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

from ..netgear_lte import DATA_KEY

DEPENDENCIES = ['netgear_lte']

SENSOR_SMS = 'sms'
SENSOR_USAGE = 'usage'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Required(CONF_SENSORS): vol.All(
        cv.ensure_list, [vol.In([SENSOR_SMS, SENSOR_USAGE])])
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info):
    """Set up Netgear LTE sensor devices."""
    modem_data = hass.data[DATA_KEY].get_modem_data(config)

    sensors = []
    for sensor_type in config[CONF_SENSORS]:
        if sensor_type == SENSOR_SMS:
            sensors.append(SMSSensor(modem_data, sensor_type))
        elif sensor_type == SENSOR_USAGE:
            sensors.append(UsageSensor(modem_data, sensor_type))

    async_add_entities(sensors, True)


@attr.s
class LTESensor(Entity):
    """Base LTE sensor entity."""

    modem_data = attr.ib()
    sensor_type = attr.ib()

    async def async_update(self):
        """Update state."""
        await self.modem_data.async_update()

    @property
    def unique_id(self):
        """Return a unique ID like 'usage_5TG365AB0078V'."""
        return "{}_{}".format(self.sensor_type, self.modem_data.serial_number)


class SMSSensor(LTESensor):
    """Unread SMS sensor entity."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Netgear LTE SMS"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.modem_data.unread_count


class UsageSensor(LTESensor):
    """Data usage sensor entity."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "MiB"

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Netgear LTE usage"

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(self.modem_data.usage / 1024**2, 1)
