"""Binary sensor platform for the Papouch integration."""

from typing import Any, override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PapouchConfigEntry
from .coordinator import PapouchDataUpdateCoordinator
from .entity import PapouchEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PapouchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data
    device = coordinator.device

    entities = [
        PapouchBinarySensor(coordinator, entry, sensor_data)
        for sensor_data in device.get_supported_binary_sensors()
    ]
    async_add_entities(entities)


class PapouchBinarySensor(PapouchEntity, BinarySensorEntity):
    """Representation of a generic Papouch binary sensor."""

    def __init__(
        self,
        coordinator: PapouchDataUpdateCoordinator,
        entry: PapouchConfigEntry,
        sensor_data: dict[str, Any],
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry)

        mac = format_mac(coordinator.device.mac_address)

        self.item_id = sensor_data["item_id"]
        self.data_key = sensor_data["type"]

        self._attr_unique_id = f"{mac}_{self.data_key}_{self.item_id}"

        if sensor_data.get("use_custom_name", False):
            self._attr_name = sensor_data["name"]
        else:
            self._attr_translation_key = sensor_data["translation"]
            if "placeholder" in sensor_data:
                self._attr_translation_placeholders = sensor_data["placeholder"]

        if "device_class" in sensor_data:
            self._attr_device_class = sensor_data["device_class"]

    @override
    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return bool(self.coordinator.data.get(self.data_key, {}).get(self.item_id) == 1)
