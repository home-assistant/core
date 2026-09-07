"""Entity representing a YouTube channel."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_TITLE, DOMAIN, MANUFACTURER
from .coordinator import YouTubeDataUpdateCoordinator


class YouTubeChannelEntity(CoordinatorEntity[YouTubeDataUpdateCoordinator]):
    """An HA implementation for YouTube entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: YouTubeDataUpdateCoordinator,
        channel_id: str,
        description: EntityDescription,
    ) -> None:
        """Initialize a YouTube entity."""
        super().__init__(coordinator)
        self.entity_description = description
        # The entry id prefix keeps unique ids unique when two accounts
        # track the same channel.
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{channel_id}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, channel_id)},
            manufacturer=MANUFACTURER,
            name=coordinator.data[ATTR_TITLE],
        )
