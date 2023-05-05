"""Support for Netgear LTE sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LTEEntity
from .const import DOMAIN
from .sensor_types import SENSOR_SMS, SENSOR_SMS_TOTAL, SENSOR_UNITS, SENSOR_USAGE

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="cell_id",
        name="Cell ID",
        icon="mdi:radio-tower",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="connection_text",
        name="Connection text",
        icon="mdi:radio-tower",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="connection_type",
        name="Connection type",
        icon="mdi:ip",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="current_band",
        name="Current band",
        icon="mdi:radio-tower",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="current_ps_service_type",
        name="Current PS service type",
        icon="mdi:radio-tower",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="radio_quality",
        name="Radio quality",
        icon="mdi:percent",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="register_network_display",
        name="Register network display",
        icon="mdi:web",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="rx_level",
        name="RX Level",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="sms",
        name="SMS",
        icon="mdi:message-processing",
    ),
    SensorEntityDescription(
        key="sms_total",
        name="SMS Total",
        icon="mdi:message-processing",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="tx_level",
        name="TX level",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="upstream",
        name="Upstream",
        icon="mdi:ip-network",
    ),
    SensorEntityDescription(
        key="usage",
        name="Usage",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netgear LTE sensor."""
    modem_data = hass.data[DOMAIN].get_modem_data(entry.data)

    sensors: list[SensorEntity] = []
    for description in SENSOR_TYPES:
        if description.key == SENSOR_SMS:
            sensors.append(SMSUnreadSensor(modem_data, description))
        elif description.key == SENSOR_SMS_TOTAL:
            sensors.append(SMSTotalSensor(modem_data, description))
        elif description.key == SENSOR_USAGE:
            sensors.append(UsageSensor(modem_data, description))
        else:
            sensors.append(GenericSensor(modem_data, description))

    async_add_entities(sensors)


class LTESensor(LTEEntity, SensorEntity):
    """Base LTE sensor entity."""

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_UNITS[self.entity_description.key]


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
        return getattr(self.modem_data.data, self.entity_description.key)
