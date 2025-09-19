"""Base entity for Habitica."""

from __future__ import annotations

from typing import TYPE_CHECKING

from habiticalib import ContentData
from yarl import URL

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import (
    HabiticaConfigEntry,
    HabiticaDataUpdateCoordinator,
    HabiticaPartyCoordinator,
)


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
            name=coordinator.data.user.profile.name,
            configuration_url=(
                URL(coordinator.config_entry.data[CONF_URL])
                / "profile"
                / coordinator.config_entry.unique_id
            ),
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
        )


class HabiticaPartyBase(CoordinatorEntity[HabiticaPartyCoordinator]):
    """Base Habitica entity representing a party."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HabiticaPartyCoordinator,
        config_entry: HabiticaConfigEntry,
        entity_description: EntityDescription,
        content: ContentData,
    ) -> None:
        """Initialize a Habitica party entity."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert config_entry.unique_id
        unique_id = f"{config_entry.unique_id}_{coordinator.data.id!s}"
        self.entity_description = entity_description
        self._attr_unique_id = f"{unique_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=NAME,
            name=coordinator.data.summary,
            identifiers={(DOMAIN, unique_id)},
            via_device=(DOMAIN, config_entry.unique_id),
        )
        self.content = content
