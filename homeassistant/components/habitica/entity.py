"""Base entity for Habitica."""

from __future__ import annotations

from typing import TYPE_CHECKING

from yarl import URL

from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import HabiticaDataUpdateCoordinator


class HabiticaBase(CoordinatorEntity[HabiticaDataUpdateCoordinator]):
    """Base Habitica entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HabiticaDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize a Habitica entity."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=NAME,
            name=coordinator.config_entry.data[CONF_NAME],
            configuration_url=(
                URL(coordinator.config_entry.data[CONF_URL])
                / "profile"
                / coordinator.config_entry.unique_id
            ),
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
        )
