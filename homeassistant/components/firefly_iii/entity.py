"""Base entity for Firefly III integration."""

from __future__ import annotations

from yarl import URL

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import FireflyDataUpdateCoordinator


class FireflyBaseEntity(CoordinatorEntity[FireflyDataUpdateCoordinator]):
    """Base class for Firefly III entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize a Firefly entity."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            configuration_url=URL(coordinator.config_entry.data[CONF_URL]),
            identifiers={
                (
                    DOMAIN,
                    f"{coordinator.config_entry.entry_id}_{self.entity_description.key}",
                )
            },
        )
