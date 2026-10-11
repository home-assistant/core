"""Base entity for the Skylight integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_FRAME_ID, CONF_FRAME_NAME, DOMAIN
from .coordinator import SkylightConfigEntry, SkylightDataUpdateCoordinator


class SkylightEntity(CoordinatorEntity[SkylightDataUpdateCoordinator]):
    """Skylight base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SkylightDataUpdateCoordinator,
        entry: SkylightConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = entry.unique_id

        frame_id: str = entry.data[CONF_FRAME_ID]
        frame_name: str = entry.data[CONF_FRAME_NAME]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, frame_id)},
            name=frame_name,
            manufacturer="Skylight",
            model="Calendar Frame",
        )
