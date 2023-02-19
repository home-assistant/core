"""base waterkotte entity."""
from pywaterkotte.ecotouch import TagData

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import EcotouchCoordinator
from .const import DOMAIN


class EcotouchEntity(CoordinatorEntity[EcotouchCoordinator]):
    """Base representation of waterkotte entities."""

    def __init__(
        self,
        coordinator: EcotouchCoordinator,
        tag: TagData,
        config_entry: ConfigEntry,
        entity_config: EntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self.entity_description = entity_config
        self.config_entry = config_entry
        self._tag = tag
        self.entity_id = f"{DOMAIN}.{entity_config.key}"
        self._attr_unique_id = f"{config_entry.unique_id}.{entity_config.key}"
        coordinator.alltags.add(tag)
        self._attr_device_info = device_info
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.coordinator.get_tag_value(self._tag)
