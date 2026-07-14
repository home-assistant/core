"""Base class for Mikrotik routers entities."""

from yarl import URL

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MikrotikDataUpdateCoordinator


class MikrotikEntity[DescriptionT: EntityDescription](
    CoordinatorEntity[MikrotikDataUpdateCoordinator]
):
    """Base class for Mikrotik entities."""

    _attr_has_entity_name = True
    entity_description: DescriptionT

    def __init__(
        self,
        coordinator: MikrotikDataUpdateCoordinator,
        description: DescriptionT,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description

        self._serial = coordinator.api.serial_number
        self._attr_device_info = DeviceInfo(
            configuration_url=URL.build(
                scheme="http",
                host=coordinator.host,
            ),
            identifiers={(DOMAIN, self._serial)},
            name=coordinator.hostname,
            manufacturer="Mikrotik",
            model=coordinator.model,
            sw_version=coordinator.firmware,
            serial_number=self._serial,
        )
        self._attr_unique_id = f"{self._serial}_{description.key}"
