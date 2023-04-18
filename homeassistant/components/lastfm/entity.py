"""LastFM Entity."""
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME
from .coordinator import LastFmUpdateCoordinator


class LastFmEntity(CoordinatorEntity[LastFmUpdateCoordinator]):
    """Representation of a LastFM entity."""

    _attr_attribution = "Data provided by Last.fm"

    def __init__(self, lastfm_coordinator: LastFmUpdateCoordinator) -> None:
        """Initialize a LastFM entity."""
        super().__init__(lastfm_coordinator)
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.last.fm",
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
        )
