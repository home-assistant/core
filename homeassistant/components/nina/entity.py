"""NINA common entity."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
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

        self._region = region
        self._warning_index = slot_id - 1
        self._region_name = region_name

        self._attr_translation_placeholders = {
            "slot_id": str(slot_id),
        }

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._region)},
            manufacturer="NINA",
            name=self._region_name,
            entry_type=DeviceEntryType.SERVICE,
        )

    def _get_active_warnings_count(self) -> int:
        """Return the number of active warnings for the region."""
        return len(self.coordinator.data[self._region])

    def _get_warning_data(self) -> NinaWarningData:
        """Return warning data."""
        return self.coordinator.data[self._region][self._warning_index]
