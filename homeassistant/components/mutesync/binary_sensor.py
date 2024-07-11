"""mütesync binary sensor entities."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
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
        user_id = coordinator.data["user-id"]
        self._attr_unique_id = f"{user_id}-{sensor_type}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, user_id)},
            manufacturer="mütesync",
            model="mutesync app",
            name="mutesync",
        )

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self._sensor_type]
