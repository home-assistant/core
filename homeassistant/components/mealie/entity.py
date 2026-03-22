"""Base class for Mealie entities."""

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MealieDataUpdateCoordinator


class MealieEntity(CoordinatorEntity[MealieDataUpdateCoordinator]):
    """Defines a base Mealie entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MealieDataUpdateCoordinator, key: str) -> None:
        """Initialize Mealie entity."""
        super().__init__(coordinator)
        unique_id = coordinator.config_entry.unique_id
        assert unique_id is not None
        self._attr_unique_id = f"{unique_id}_{key}"
        host = coordinator.config_entry.data[CONF_HOST]
        if not host.startswith(("http://", "https://")):
            configuration_url = f"https://{host}"
        else:
            configuration_url = host
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(unique_id))},
            configuration_url=configuration_url,
        )
