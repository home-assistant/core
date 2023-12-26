"""Support for Netgear LTE sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LTEEntity
from .sensor_types import (
    ALL_SENSORS,
    SENSOR_SMS,
    SENSOR_SMS_TOTAL,
    SENSOR_UNITS,
    SENSOR_USAGE,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netgear LTE sensor."""
    modem_data = hass.data[DOMAIN].get_modem_data(entry.data)

    sensors: list[SensorEntity] = []
    for sensor in ALL_SENSORS:
        if sensor == SENSOR_SMS:
            sensors.append(SMSUnreadSensor(modem_data, sensor))
        elif sensor == SENSOR_SMS_TOTAL:
            sensors.append(SMSTotalSensor(modem_data, sensor))
        elif sensor == SENSOR_USAGE:
            sensors.append(UsageSensor(modem_data, sensor))
        else:
            sensors.append(GenericSensor(modem_data, sensor))

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
