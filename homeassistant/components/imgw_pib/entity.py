"""Define the IMGW-PIB entity."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION
from .coordinator import ImgwPibDataUpdateCoordinator


class ImgwPibEntity(CoordinatorEntity[ImgwPibDataUpdateCoordinator]):
    """Define IMGW-PIB entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ImgwPibDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return the value reported by the sensor."""
        if self.state is not None:
            return super().available

        return False
