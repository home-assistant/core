"""Support for Netgear LTE sensors."""
import logging

import attr

from homeassistant.components.sensor import DOMAIN
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import CONF_MONITORED_CONDITIONS, DATA_KEY, DISPATCHER_NETGEAR_LTE
from .sensor_types import SENSOR_SMS, SENSOR_USAGE, SENSOR_UNITS

DEPENDENCIES = ['netgear_lte']

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info):
    """Set up Netgear LTE sensor devices."""
    if discovery_info is None:
        return

    modem_data = hass.data[DATA_KEY].get_modem_data(discovery_info)

    if not modem_data or not modem_data.data:
        raise PlatformNotReady

    sensor_conf = discovery_info[DOMAIN]
    monitored_conditions = sensor_conf[CONF_MONITORED_CONDITIONS]

    sensors = []
    for sensor_type in monitored_conditions:
        if sensor_type == SENSOR_SMS:
            sensors.append(SMSSensor(modem_data, sensor_type))
        elif sensor_type == SENSOR_USAGE:
            sensors.append(UsageSensor(modem_data, sensor_type))
        else:
            sensors.append(GenericSensor(modem_data, sensor_type))

    async_add_entities(sensors)


@attr.s
class LTESensor(Entity):
    """Base LTE sensor entity."""

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

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_UNITS[self.sensor_type]


class SMSSensor(LTESensor):
    """Unread SMS sensor entity."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return sum(1 for x in self.modem_data.data.sms if x.unread)


class UsageSensor(LTESensor):
    """Data usage sensor entity."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(self.modem_data.data.usage / 1024**2, 1)


class GenericSensor(LTESensor):
    """Sensor entity with raw state."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self.modem_data.data, self.sensor_type)
