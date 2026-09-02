"""What every Ecowitt WS90 entity shares."""

from dataclasses import dataclass

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import WS90DataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class WS90EntityDescription(EntityDescription):
    """Which component of the sensor array an entity reads through."""

    component: str  # attribute name on WS90, e.g. 'sensors'


class WS90Entity(CoordinatorEntity[WS90DataUpdateCoordinator]):
    """An entity backed by one component of the WS90."""

    _attr_has_entity_name = True
    entity_description: WS90EntityDescription

    def __init__(
        self,
        coordinator: WS90DataUpdateCoordinator,
        entity_description: WS90EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        info = coordinator.device.info
        self._attr_unique_id = f"{info.device_id:08x}_{entity_description.key}"
        self._attr_device_info = coordinator.device_info
