"""La Marzocco image platform."""

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import LaMarzoccoConfigEntry, LaMarzoccoConfigUpdateCoordinator
from .entity import LaMarzoccoBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up image entities."""
    coordinator = entry.runtime_data.config_coordinator

    async_add_entities([LaMarzoccoImageEntity(coordinator)])


class LaMarzoccoImageEntity(LaMarzoccoBaseEntity, ImageEntity):
    """Image representation for La Marzocco."""

    _attr_translation_key = "machine_image"
    _attr_content_type = "image/png"

    def __init__(
        self,
        coordinator: LaMarzoccoConfigUpdateCoordinator,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, "machine_image")
        ImageEntity.__init__(self, coordinator.hass)
        self._attr_image_last_updated = dt_util.utcnow()

    @property
    def image_url(self) -> str:
        """Return the image URL."""
        return self.coordinator.device.dashboard.image_url
