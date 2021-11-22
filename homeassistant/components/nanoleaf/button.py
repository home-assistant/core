"""Support for Nanoleaf buttons."""

from aionanoleaf import Nanoleaf

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import NanoleafEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nanoleaf button."""
    nanoleaf: Nanoleaf = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NanoleafIdentifyButton(nanoleaf)])


class NanoleafIdentifyButton(NanoleafEntity, ButtonEntity):
    """Representation of a Nanoleaf identify button."""

    def __init__(self, nanoleaf: Nanoleaf) -> None:
        """Initialize the Nanoleaf button."""
        super().__init__(nanoleaf)
        self._attr_unique_id = f"{nanoleaf.serial_no}_identify"
        self._attr_name = f"Identify {nanoleaf.name}"
        self._attr_icon = "mdi:magnify"
        self._attr_entity_category = ENTITY_CATEGORY_CONFIG

    async def async_press(self) -> None:
        """Identify the Nanoleaf."""
        await self._nanoleaf.identify()
