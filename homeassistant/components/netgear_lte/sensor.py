"""Support for Netgear LTE sensors."""
import logging

from homeassistant.components.sensor import DOMAIN
from homeassistant.exceptions import PlatformNotReady

from . import CONF_MONITORED_CONDITIONS, DATA_KEY, LTEEntity
from .sensor_types import SENSOR_SMS, SENSOR_SMS_TOTAL, SENSOR_UNITS, SENSOR_USAGE

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info):
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
            sensors.append(SMSUnreadSensor(modem_data, sensor_type))
        elif sensor_type == SENSOR_SMS_TOTAL:
            sensors.append(SMSTotalSensor(modem_data, sensor_type))
        elif sensor_type == SENSOR_USAGE:
            sensors.append(UsageSensor(modem_data, sensor_type))
        else:
            sensors.append(GenericSensor(modem_data, sensor_type))

    async_add_entities(sensors)


class LTESensor(LTEEntity):
    """Base LTE sensor entity."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_UNITS[self.sensor_type]


class SMSUnreadSensor(LTESensor):
    """Unread SMS sensor entity."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return sum(1 for x in self.modem_data.data.sms if x.unread)


class SMSTotalSensor(LTESensor):
    """Total SMS sensor entity."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return len(self.modem_data.data.sms)


class UsageSensor(LTESensor):
    """Data usage sensor entity."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(self.modem_data.data.usage / 1024 ** 2, 1)


class GenericSensor(LTESensor):
    """Sensor entity with raw state."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self.modem_data.data, self.sensor_type)
