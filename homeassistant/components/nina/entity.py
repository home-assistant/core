"""NINA common entity."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NINADataUpdateCoordinator, NinaWarningData


class NinaEntity(CoordinatorEntity[NINADataUpdateCoordinator]):
    """Base class for NINA entities."""

    def __init__(
        self,
        coordinator: NINADataUpdateCoordinator,
        region: str,
        region_name: str,
        slot_id: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._region: str = region
        self._warning_index: int = slot_id - 1

        self._active_warning_count: int = len(coordinator.data[self._region])

        self._attr_translation_placeholders = {
            "region_name": region_name,
            "slot_id": str(slot_id),
        }
        self._attr_device_info = coordinator.device_info

    def _get_warning_data(self) -> NinaWarningData:
        """Return warning data."""
        return self.coordinator.data[self._region][self._warning_index]
