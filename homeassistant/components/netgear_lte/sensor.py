"""Support for Netgear LTE sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import CONF_MONITORED_CONDITIONS, CONF_SENSOR, DATA_KEY, LTEEntity
from .sensor_types import SENSOR_SMS, SENSOR_SMS_TOTAL, SENSOR_UNITS, SENSOR_USAGE


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Netgear LTE sensor devices."""
    if discovery_info is None:
        return

    modem_data = hass.data[DATA_KEY].get_modem_data(discovery_info)

    if not modem_data or not modem_data.data:
        raise PlatformNotReady

    sensor_conf = discovery_info[CONF_SENSOR]
    monitored_conditions = sensor_conf[CONF_MONITORED_CONDITIONS]

    sensors: list[SensorEntity] = []
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


class LTESensor(LTEEntity, SensorEntity):
    """Base LTE sensor entity."""

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_UNITS[self.sensor_type]


class SMSUnreadSensor(LTESensor):
    """Unread SMS sensor entity."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return sum(1 for x in self.modem_data.data.sms if x.unread)


class SMSTotalSensor(LTESensor):
    """Total SMS sensor entity."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return len(self.modem_data.data.sms)


class UsageSensor(LTESensor):
    """Data usage sensor entity."""

    _attr_device_class = SensorDeviceClass.DATA_SIZE

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return round(self.modem_data.data.usage / 1024**2, 1)


class GenericSensor(LTESensor):
    """Sensor entity with raw state."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return getattr(self.modem_data.data, self.sensor_type)
