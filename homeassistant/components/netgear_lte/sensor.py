"""Support for Netgear LTE sensors."""
import logging

from homeassistant.exceptions import PlatformNotReady

from . import DATA_KEY, LTEEntity
from . import sensor_types

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info):
    """Set up Netgear LTE sensor devices."""
    if discovery_info is None:
        return

    modem_data = hass.data[DATA_KEY].get_modem_data(discovery_info)

    if not modem_data or not modem_data.data:
        raise PlatformNotReady

    sensors = []

    for sensor_type in sensor_types.ALL_SENSORS:
        if sensor_type == sensor_types.SENSOR_SMS:
            sensors.append(SMSUnreadSensor(modem_data, sensor_type))
        elif sensor_type == sensor_types.SENSOR_SMS_TOTAL:
            sensors.append(SMSTotalSensor(modem_data, sensor_type))
        elif sensor_type == sensor_types.SENSOR_USAGE:
            sensors.append(UsageSensor(modem_data, sensor_type))

    for sensor_type in modem_data.data.items:
        sensors.append(GenericSensor(modem_data, sensor_type))

    async_add_entities(sensors)


class LTESensor(LTEEntity):
    """Base LTE sensor entity."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement (if known)."""
        return sensor_types.SENSOR_UNITS.get(self.sensor_type)


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
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(self.modem_data.data.usage / 1024 ** 2, 1)


class GenericSensor(LTESensor):
    """Sensor entity with raw state."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.modem_data.data.items.get(self.sensor_type)
