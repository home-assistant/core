"""Base entity for the APsystems Lake_6 integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN
from .coordinator import Lake6Coordinator


class Lake6Entity(CoordinatorEntity[Lake6Coordinator]):
    """Base entity shared by every Lake_6 platform.

    Only the device identity is shared here; each platform supplies its own
    entity description and unique id.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: Lake6Coordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.dev_id)},
            manufacturer="APsystems",
            # type comes from /devices and is shown as reported, with no mapping.
            model=device.device_type,
            serial_number=device.dev_id,
            # The client layer already turned an empty firmware version into
            # None, which hides the firmware row on the device page.
            sw_version=device.sw_version,
        )

    @property
    def device_id(self) -> str:
        """Return the device id used to build entity unique ids."""
        return self.coordinator.device.dev_id
