"""A entity class for Bravia TV integration."""
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BraviaTVCoordinator
from .const import ATTR_MANUFACTURER, DOMAIN


class BraviaTVEntity(CoordinatorEntity[BraviaTVCoordinator]):
    """BraviaTV entity class."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BraviaTVCoordinator,
        unique_id: str,
        model: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=ATTR_MANUFACTURER,
            model=model,
            name=f"{ATTR_MANUFACTURER} {model}",
        )
