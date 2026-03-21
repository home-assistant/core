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

        self._region: str = region
        self._warning_index: int = slot_id - 1
        self._region_name: str = region_name

        self._attr_translation_placeholders = {
            "slot_id": str(slot_id),
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._region}")},
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
