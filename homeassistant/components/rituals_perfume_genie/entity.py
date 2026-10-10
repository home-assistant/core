"""Base class for Rituals Perfume Genie diffuser entity."""

from typing import override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RitualsDataUpdateCoordinator

MANUFACTURER = "Rituals Cosmetics"
MODEL = "The Perfume Genie"
MODEL2 = "The Perfume Genie 2.0"


class DiffuserEntity(CoordinatorEntity[RitualsDataUpdateCoordinator]):
    """Representation of a diffuser entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RitualsDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Init from config, hookup diffuser and coordinator."""
        super().__init__(coordinator)
        self.entity_description = description

        hub = coordinator.data.hub
        firmware = hub.firmware.current if hub.firmware else None

        self._attr_unique_id = f"{coordinator.hublot}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.hublot)},
            manufacturer=MANUFACTURER,
            model=MODEL if hub.has_battery else MODEL2,
            name=hub.name,
            sw_version=str(firmware) if firmware else None,
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.coordinator.data.hub.is_online is not False
