"""Support for Wallbox update platform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CHARGER_CURRENT_VERSION_KEY,
    CHARGER_DATA_KEY,
    CHARGER_LATEST_VERSION_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
    CHARGER_SOFTWARE_KEY,
    DOMAIN,
)
from .coordinator import WallboxCoordinator
from .entity import WallboxEntity


@dataclass(frozen=True, kw_only=True)
class WallboxUpdateEntityDescription(UpdateEntityDescription):
    """Describes Wallbox update entity."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wallbox update entities."""
    coordinator: WallboxCoordinator = hass.data[DOMAIN][entry.entry_id]
    description = WallboxUpdateEntityDescription(
        key=CHARGER_SOFTWARE_KEY,
        translation_key="firmware",
    )

    entities = [WallboxBoxUpdateEntity(coordinator, description)]

    async_add_entities(entities)


class WallboxBoxUpdateEntity(WallboxEntity, UpdateEntity):
    """Mixin for update entity specific attributes."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_supported_features = UpdateEntityFeature.INSTALL
    entity_description: WallboxUpdateEntityDescription

    def __init__(
        self,
        coordinator: WallboxCoordinator,
        description: WallboxUpdateEntityDescription,
    ) -> None:
        """Init Wallbox connectivity class."""
        super().__init__(coordinator)
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_unique_id = f"{description.key}-{coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY]}"

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return str(
            self.coordinator.data[CHARGER_SOFTWARE_KEY][CHARGER_CURRENT_VERSION_KEY]
        )

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if self.coordinator.data[CHARGER_SOFTWARE_KEY][CHARGER_LATEST_VERSION_KEY]:
            return str(
                self.coordinator.data[CHARGER_SOFTWARE_KEY][CHARGER_LATEST_VERSION_KEY]
            )
        return str(
            self.coordinator.data[CHARGER_SOFTWARE_KEY][CHARGER_CURRENT_VERSION_KEY]
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self.coordinator.async_trigger_firmware_update()
