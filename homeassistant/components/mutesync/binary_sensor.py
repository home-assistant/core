"""mütesync binary sensor entities."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

SENSORS = (
    "in_meeting",
    "muted",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the mütesync button."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [MuteStatus(coordinator, sensor_type) for sensor_type in SENSORS], True
    )


class MuteStatus(update_coordinator.CoordinatorEntity, BinarySensorEntity):
    """Mütesync binary sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, sensor_type):
        """Initialize our sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_translation_key = sensor_type

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return f"{self.coordinator.data['user-id']}-{self._sensor_type}"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self._sensor_type]

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info of the sensor."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.coordinator.data["user-id"])},
            manufacturer="mütesync",
            model="mutesync app",
            name="mutesync",
        )
