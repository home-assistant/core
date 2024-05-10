"""Aquacell entity."""

from aioaquacell import Softener

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AquacellCoordinator


class AquacellEntity(CoordinatorEntity[AquacellCoordinator]):
    """Representation of an aquacell entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AquacellCoordinator,
        softener: Softener,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the aquacell entity."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{softener.dsn}-{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            name=softener.name,
            hw_version=softener.fwVersion,
            identifiers={(DOMAIN, str(softener.dsn))},
            manufacturer=softener.brand,
            model=softener.ssn,
            serial_number=softener.dsn,
        )
