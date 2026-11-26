"""Support for the Stookwijzer advice map image."""

from typing import override

from stookwijzer import MapOptions

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ADVICE_LEVELS, DOMAIN
from .coordinator import StookwijzerConfigEntry, StookwijzerCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StookwijzerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Stookwijzer image from a config entry."""
    async_add_entities([StookwijzerImage(entry)])


class StookwijzerImage(CoordinatorEntity[StookwijzerCoordinator], ImageEntity):
    """Image showing the Stookwijzer advice areas on a map."""

    _attr_attribution = "Data provided by atlasleefomgeving.nl"
    _attr_content_type = "image/png"
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_translation_key = "map"

    def __init__(self, entry: StookwijzerConfigEntry) -> None:
        """Initialize the Stookwijzer image."""
        super().__init__(entry.runtime_data)
        ImageEntity.__init__(self, entry.runtime_data.hass)
        self._attr_unique_id = f"{entry.entry_id}_map"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Atlas Leefomgeving",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.atlasleefomgeving.nl/stookwijzer",
        )
        self._attr_image_last_updated = dt_util.utcnow()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Mark the image as changed, the client renders a new map after an update."""
        self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    @override
    async def async_image(self) -> bytes | None:
        """Return the map, rendered by the client once per coordinator update."""
        translations = await async_get_translations(
            self.hass, self.hass.config.language, "common", {DOMAIN}
        )
        labels = {
            level: translations[f"component.{DOMAIN}.common.legend_{level}"]
            for level in ADVICE_LEVELS
        }
        options = MapOptions(labels=labels)
        if (result := await self.coordinator.client.async_get_map(options)) is None:
            return None
        image: bytes = result.image
        return image
