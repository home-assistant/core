"""Support for PJLink projectors."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PJLinkUpdateCoordinator
from .device import PJLinkDevice


class PJLinkEntity(CoordinatorEntity[PJLinkUpdateCoordinator]):
    """Representation of a PJLink entity with a coordinator."""

    _device: PJLinkDevice

    def __init__(self, coordinator: PJLinkUpdateCoordinator) -> None:
        """Initialize the projector."""
        super().__init__(coordinator)

        self._device = coordinator.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.projector_unique_id)},
            manufacturer=coordinator.manufacturer,
            model=coordinator.model,
            name=self.device.name,
            configuration_url=f"http://{coordinator.device.host}/",
            via_device=(DOMAIN, coordinator.projector_unique_id),
        )

    @property
    def device(self) -> PJLinkDevice:
        """Get the device."""
        return self._device
