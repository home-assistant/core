"""Support for SMS dongle sensor."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    GATEWAY,
    NETWORK_COORDINATOR,
    NETWORK_SENSORS,
    SIGNAL_COORDINATOR,
    SIGNAL_SENSORS,
    SMS_GATEWAY,
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
    entities = []
    for description in SIGNAL_SENSORS.values():
        entities.append(
            DeviceSensor(
                signal_coordinator,
                description,
                unique_id,
            )
        )
    for description in NETWORK_SENSORS.values():
        entities.append(
            DeviceSensor(
                network_coordinator,
                description,
                unique_id,
            )
        )
    async_add_entities(entities, True)


class DeviceSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a device sensor."""

    def __init__(self, coordinator, description, unique_id):
        """Initialize the device sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name="SMS Gateway",
        )
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self):
        """Return the state of the device."""
        return self.coordinator.data.get(self.entity_description.key)
