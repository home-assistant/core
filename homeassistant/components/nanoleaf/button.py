"""Support for Nanoleaf buttons."""

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NanoleafConfigEntry
from .coordinator import NanoleafCoordinator
from .entity import NanoleafEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NanoleafConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Nanoleaf button."""
    async_add_entities([NanoleafIdentifyButton(entry.runtime_data)])


class NanoleafIdentifyButton(NanoleafEntity, ButtonEntity):
    """Representation of a Nanoleaf identify button."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = ButtonDeviceClass.IDENTIFY

    def __init__(self, coordinator: NanoleafCoordinator) -> None:
        """Initialize the Nanoleaf button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._nanoleaf.serial_no}_identify"

    async def async_press(self) -> None:
        """Identify the Nanoleaf."""
        await self._nanoleaf.identify()
