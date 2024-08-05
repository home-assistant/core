"""Support for SMS dongle sensor."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, GATEWAY, NETWORK_COORDINATOR, SIGNAL_COORDINATOR, SMS_GATEWAY

SIGNAL_SENSORS = (
    SensorEntityDescription(
        key="SignalStrength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="SignalPercent",
        translation_key="signal_percent",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=True,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="BitErrorRate",
        translation_key="bit_error_rate",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

NETWORK_SENSORS = (
    SensorEntityDescription(
        key="NetworkName",
        translation_key="network_name",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="State",
        translation_key="state",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="NetworkCode",
        translation_key="network_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="CID",
        translation_key="cid",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="LAC",
        translation_key="lac",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all device sensors."""
    sms_data = hass.data[DOMAIN][SMS_GATEWAY]
    signal_coordinator = sms_data[SIGNAL_COORDINATOR]
    network_coordinator = sms_data[NETWORK_COORDINATOR]
    gateway = sms_data[GATEWAY]
    unique_id = str(await gateway.get_imei_async())
    entities = [
        DeviceSensor(signal_coordinator, description, unique_id, gateway)
        for description in SIGNAL_SENSORS
    ]
    entities.extend(
        DeviceSensor(network_coordinator, description, unique_id, gateway)
        for description in NETWORK_SENSORS
    )
    async_add_entities(entities, True)


class DeviceSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a device sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, description, unique_id, gateway):
        """Initialize the device sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name="SMS Gateway",
            manufacturer=gateway.manufacturer,
            model=gateway.model,
            sw_version=gateway.firmware,
        )
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self):
        """Return the state of the device."""
        return self.coordinator.data.get(self.entity_description.key)
