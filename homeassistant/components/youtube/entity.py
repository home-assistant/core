"""Entity representing a YouTube channel."""

from typing import Any, override

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CHANNEL_ID, DOMAIN, MANUFACTURER
from .coordinator import YouTubeDataUpdateCoordinator


class YouTubeChannelEntity(CoordinatorEntity[YouTubeDataUpdateCoordinator]):
    """An HA implementation for YouTube entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: YouTubeDataUpdateCoordinator,
        subentry: ConfigSubentry,
        description: EntityDescription,
    ) -> None:
        """Initialize a YouTube entity."""
        super().__init__(coordinator)
        self.entity_description = description
        channel_id = subentry.data[CONF_CHANNEL_ID]
        self._channel_id = channel_id
        # The entry id prefix keeps unique ids unique when two accounts
        # track the same channel.
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{channel_id}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, channel_id)},
            manufacturer=MANUFACTURER,
            name=subentry.title,
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self._channel_id in self.coordinator.data

    @property
    def _channel_data(self) -> Any:
        """Return the channel data."""
        return self.coordinator.data[self._channel_id]
