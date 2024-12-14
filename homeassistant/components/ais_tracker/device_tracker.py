"""Device tracker for AIS tracker."""

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MMSIS, DOMAIN
from .coordinator import AisTrackerConfigEntry, AisTrackerCoordinator
from .entity import AistrackerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AisTrackerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for AIS tracker."""
    coordinator = entry.runtime_data

    async_add_entities(
        AisTrackerEntity(coordinator, mmsi) for mmsi in entry.data[CONF_MMSIS]
    )


class AisTrackerEntity(AistrackerEntity, TrackerEntity):
    """Represent a tracked device."""

    _attr_translation_key = "vessel"
    _attr_name = None

    def __init__(
        self,
        coordinator: AisTrackerCoordinator,
        mmsi: str,
    ) -> None:
        """Set up AIS tracker entity."""
        super().__init__(coordinator, mmsi)
        self._attr_unique_id = f"{DOMAIN}_{mmsi}"

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        if (data := self.data) is not None and (value := data.get("lat")) is not None:
            return float(value)
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        if (data := self.data) is not None and (value := data.get("lon")) is not None:
            return float(value)
        return None

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS
