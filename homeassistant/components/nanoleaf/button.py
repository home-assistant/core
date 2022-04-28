"""Support for Nanoleaf buttons."""

from aionanoleaf import Nanoleaf

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import NanoleafEntryData
from .const import DOMAIN
from .entity import NanoleafEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nanoleaf button."""
    entry_data: NanoleafEntryData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [NanoleafIdentifyButton(entry_data.device, entry_data.coordinator)]
    )


class NanoleafIdentifyButton(NanoleafEntity, ButtonEntity):
    """Representation of a Nanoleaf identify button."""

    def __init__(self, nanoleaf: Nanoleaf, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the Nanoleaf button."""
        super().__init__(nanoleaf, coordinator)
        self._attr_unique_id = f"{nanoleaf.serial_no}_identify"
        self._attr_name = f"Identify {nanoleaf.name}"
        self._attr_icon = "mdi:magnify"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Identify the Nanoleaf."""
        await self._nanoleaf.identify()
