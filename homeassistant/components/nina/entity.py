"""NINA common entity."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NINADataUpdateCoordinator, NinaWarningData


class NinaEntity(CoordinatorEntity[NINADataUpdateCoordinator]):
    """Base class for NINA entities."""

    def __init__(
        self, coordinator: NINADataUpdateCoordinator, region: str, slot_id: int
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._region: str = region
        self._warning_index: int = slot_id - 1

        self._active_warning_count: int = len(coordinator.data[self._region])

    def _get_warning_data(self) -> NinaWarningData:
        """Return warning data."""
        return self.coordinator.data[self._region][self._warning_index]
