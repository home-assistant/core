"""Binary sensor platform for Wireless Sensor Tags."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WirelessTagDataUpdateCoordinator

PARALLEL_UPDATES = 0

BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    BinarySensorEntityDescription(
        key="presence",
        device_class=BinarySensorDeviceClass.PRESENCE,
    ),
    BinarySensorEntityDescription(
        key="door",
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    BinarySensorEntityDescription(
        key="moisture",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    BinarySensorEntityDescription(
        key="cold",
        device_class=BinarySensorDeviceClass.COLD,
    ),
    BinarySensorEntityDescription(
        key="heat",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    BinarySensorEntityDescription(
        key="light",
        device_class=BinarySensorDeviceClass.LIGHT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wireless Tag binary sensor platform."""
    coordinator: WirelessTagDataUpdateCoordinator = config_entry.runtime_data

    def _async_add_entities_for_tags(tag_ids: set[str]) -> None:
        """Add binary sensor entities for the given tag IDs."""
        entities = [
            WirelessTagBinarySensor(coordinator, tag_id, description)
            for tag_id in tag_ids
            if tag_id in coordinator.data
            for description in BINARY_SENSOR_DESCRIPTIONS
            if coordinator.data[tag_id].get(description.key) is not None
        ]
        async_add_entities(entities)

    # Register callback for dynamic device addition
    coordinator.new_devices_callbacks.append(_async_add_entities_for_tags)

    # Add entities for existing devices
    if coordinator.data:
        _async_add_entities_for_tags(set(coordinator.data.keys()))


class WirelessTagBinarySensor(
    CoordinatorEntity[WirelessTagDataUpdateCoordinator], BinarySensorEntity
):
    """Implementation of a Wireless Tag binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WirelessTagDataUpdateCoordinator,
        tag_id: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._tag_id = tag_id

        # Set unique ID
        tag_data = coordinator.data[tag_id]
        self._attr_unique_id = f"{tag_data['uuid']}_{description.key}"

        # Set device info (static)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tag_data["uuid"])},
            name=tag_data["name"],
            manufacturer="Wireless Sensor Tag",
            model="Wireless Sensor Tag",
            sw_version=tag_data.get("version"),
            serial_number=tag_data["uuid"],
        )

        # Initialize state
        self._update_from_coordinator()

    def _update_from_coordinator(self) -> None:
        """Update entity state from coordinator data."""
        if self._tag_id not in self.coordinator.data:
            self._attr_available = False
            self._attr_is_on = None
            return

        tag_data = self.coordinator.data[self._tag_id]
        self._attr_available = tag_data["is_alive"]
        self._attr_is_on = tag_data.get(self.entity_description.key)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        self.async_write_ha_state()
