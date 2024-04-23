"""Creates the device tracker entity for the mower."""

from typing import TYPE_CHECKING

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker platform."""
    coordinator: AutomowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AutomowerDeviceTrackerEntity(mower_id, coordinator)
        for mower_id in coordinator.data
        if coordinator.data[mower_id].capabilities.position
    )


class AutomowerDeviceTrackerEntity(AutomowerBaseEntity, TrackerEntity):
    """Defining the AutomowerDeviceTrackerEntity."""

    _attr_name = None

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Initialize AutomowerDeviceTracker."""
        super().__init__(mower_id, coordinator)
        self._attr_unique_id = mower_id

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        return SourceType.GPS

    @property
    def latitude(self) -> float:
        """Return latitude value of the device."""
        if TYPE_CHECKING:
            assert self.mower_attributes.positions is not None
        return self.mower_attributes.positions[0].latitude

    @property
    def longitude(self) -> float:
        """Return longitude value of the device."""
        if TYPE_CHECKING:
            assert self.mower_attributes.positions is not None
        return self.mower_attributes.positions[0].longitude
