"""Entity representing a Dremel 3D Printer."""

from dremel3dpy import Dremel3DPrinter

from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Dremel3DPrinterDataUpdateCoordinator


class Dremel3DPrinterEntity(CoordinatorEntity[Dremel3DPrinterDataUpdateCoordinator]):
    """Defines a Dremel 3D Printer device entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the base device entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Dremel printer."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._api.get_serial_number())},
            manufacturer=self._api.get_manufacturer(),
            model=self._api.get_model(),
            name=self._api.get_title(),
            sw_version=self._api.get_firmware_version(),
        )

    @property
    def _api(self) -> Dremel3DPrinter:
        """Return to api from coordinator."""
        return self.coordinator.api
