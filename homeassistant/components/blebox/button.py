"""BleBox button entities implementation."""

import blebox_uniapi.button

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BleBoxConfigEntry
from .entity import BleBoxEntity

BUTTON_TYPES: dict[str, ButtonEntityDescription] = {
    "up": ButtonEntityDescription(key="up", translation_key="up"),
    "down": ButtonEntityDescription(key="down", translation_key="down"),
    "fav": ButtonEntityDescription(key="fav", translation_key="fav"),
    "open": ButtonEntityDescription(key="open", translation_key="open"),
    "close": ButtonEntityDescription(key="close", translation_key="close"),
}

_DEFAULT_BUTTON = ButtonEntityDescription(key="button")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BleBoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a BleBox button entry."""
    entities = [
        BleBoxButtonEntity(feature)
        for feature in config_entry.runtime_data.features.get("buttons", [])
    ]
    async_add_entities(entities, True)


class BleBoxButtonEntity(BleBoxEntity[blebox_uniapi.button.Button], ButtonEntity):
    """Representation of BleBox buttons."""

    def __init__(self, feature: blebox_uniapi.button.Button) -> None:
        """Initialize a BleBox button feature."""
        super().__init__(feature)
        self.entity_description = self._get_description()

    def _get_description(self) -> ButtonEntityDescription:
        """Return the description matching this button's query string."""
        for key, description in BUTTON_TYPES.items():
            if key in self._feature.query_string:
                return description
        return _DEFAULT_BUTTON

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._feature.set()
