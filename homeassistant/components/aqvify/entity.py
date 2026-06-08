"""Defines a base Aqvify entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AqvifyCoordinator


class AqvifyBaseEntity(CoordinatorEntity[AqvifyCoordinator]):
    """Defines a base Aqvify entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AqvifyCoordinator,
        description: EntityDescription,
        device_key: str,
    ) -> None:
        """Initialize the Aqvify entity."""
        super().__init__(coordinator)

        account_id = self.coordinator.config_entry.unique_id
        self.device_key = device_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{account_id}_{device_key}")},
            name=coordinator.data.devices.devices[device_key].name,
            manufacturer="Aqvify",
            configuration_url="https://app.aqvify.com",
            serial_number=device_key,
        )
        self._attr_unique_id = f"{account_id}_{device_key}_{description.key}"
        self.entity_description = description
