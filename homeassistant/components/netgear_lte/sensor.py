"""Support for Netgear LTE sensors."""
import logging

import attr

from homeassistant.components.sensor import DOMAIN
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import CONF_MONITORED_CONDITIONS, DATA_KEY, DISPATCHER_NETGEAR_LTE
from .sensor_types import SENSOR_SMS, SENSOR_USAGE

DEPENDENCIES = ['netgear_lte']

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info):
    """Set up Netgear LTE sensor devices."""
    if discovery_info is None:
        return

    modem_data = hass.data[DATA_KEY].get_modem_data(discovery_info)

    if not modem_data:
        raise PlatformNotReady

    sensor_conf = discovery_info[DOMAIN]
    monitored_conditions = sensor_conf[CONF_MONITORED_CONDITIONS]

    sensors = []
    for sensor_type in monitored_conditions:
        if sensor_type == SENSOR_SMS:
            sensors.append(SMSSensor(modem_data, sensor_type))
        elif sensor_type == SENSOR_USAGE:
            sensors.append(UsageSensor(modem_data, sensor_type))

    async_add_entities(sensors)


@attr.s
class LTESensor(Entity):
    """Base LTE sensor entity."""

    modem_data = attr.ib()
    sensor_type = attr.ib()

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
        if self.modem_data.usage is None:
            return None

        return round(self.modem_data.usage / 1024**2, 1)
