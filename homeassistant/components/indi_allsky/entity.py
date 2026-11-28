"""Base entity for the INDI Allsky integration."""

from aioindiallsky import IndiAllSkyAuthError, IndiAllSkyError

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IndiAllSkyConfigEntry, IndiAllSkyDataUpdateCoordinator


class IndiAllSkyEntity(CoordinatorEntity[IndiAllSkyDataUpdateCoordinator]):
    """Base class for INDI Allsky entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IndiAllSkyDataUpdateCoordinator,
        entry: IndiAllSkyConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def _async_fetch_image(self, endpoint: str) -> bytes | None:
        """Fetch an image from the client, triggering reauth on auth failure."""
        try:
            return await self.coordinator.client.fetch_image(endpoint)
        except IndiAllSkyAuthError:
            self._entry.async_start_reauth(self.hass)
            return None
        except IndiAllSkyError:
            return None
