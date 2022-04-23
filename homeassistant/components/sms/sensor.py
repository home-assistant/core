"""Support for SMS dongle sensor."""
import logging

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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all GSM sensors."""
    sms_data = hass.data[DOMAIN][SMS_GATEWAY]
    signal_coordinator = sms_data[SIGNAL_COORDINATOR]
    network_coordinator = sms_data[NETWORK_COORDINATOR]
    gateway = sms_data[GATEWAY]
    imei = await gateway.get_imei_async()
    entities = []
    for _, description in SIGNAL_SENSORS.items():
        entities.append(
            GSMSensor(
                signal_coordinator,
                description,
                str(imei),
            )
        )
    for _, description in NETWORK_SENSORS.items():
        entities.append(
            GSMSensor(
                network_coordinator,
                description,
                str(imei),
            )
        )
    async_add_entities(entities, True)


class GSMSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a GSM sensor."""

    def __init__(self, coordinator, description, unique_id):
        """Initialize the GSM sensor."""
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
