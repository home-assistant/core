"""Creates the device tracker entity for the mower."""

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AutomowerConfigEntry
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker platform."""
    coordinator = entry.runtime_data

    def _async_add_new_devices(mower_ids: set[str]) -> None:
        async_add_entities(
            AutomowerDeviceTrackerEntity(mower_id, coordinator)
            for mower_id in mower_ids
            if coordinator.data[mower_id].capabilities.position
        )

    coordinator.new_devices_callbacks.append(_async_add_new_devices)
    _async_add_new_devices(set(coordinator.data))


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
    def latitude(self) -> float:
        """Return latitude value of the device."""
        return self.mower_attributes.positions[0].latitude

    @property
    def longitude(self) -> float:
        """Return longitude value of the device."""
        return self.mower_attributes.positions[0].longitude
