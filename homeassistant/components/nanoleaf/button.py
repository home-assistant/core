"""Support for Nanoleaf buttons."""

from aionanoleaf import Nanoleaf

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
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

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = ButtonDeviceClass.IDENTIFY

    def __init__(
        self, nanoleaf: Nanoleaf, coordinator: DataUpdateCoordinator[None]
    ) -> None:
        """Initialize the Nanoleaf button."""
        super().__init__(nanoleaf, coordinator)
        self._attr_unique_id = f"{nanoleaf.serial_no}_identify"

    async def async_press(self) -> None:
        """Identify the Nanoleaf."""
        await self._nanoleaf.identify()
