"""Support for Overkiz covers - shutters etc."""
from pyoverkiz.enums import OverkizCommand, UIClass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .const import DOMAIN
from .cover_entities.awning import Awning
from .cover_entities.generic_cover import OverkizGenericCover
from .cover_entities.vertical_cover import LowSpeedCover, VerticalCover


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Overkiz covers from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]

    entities: list[OverkizGenericCover] = [
        Awning(device.device_url, data.coordinator)
        for device in data.platforms[Platform.COVER]
        if device.ui_class == UIClass.AWNING
    ]

    entities += [
        VerticalCover(device.device_url, data.coordinator)
        for device in data.platforms[Platform.COVER]
        if device.ui_class != UIClass.AWNING
    ]

    entities += [
        LowSpeedCover(device.device_url, data.coordinator)
        for device in data.platforms[Platform.COVER]
        if OverkizCommand.SET_CLOSURE_AND_LINEAR_SPEED in device.definition.commands
    ]

    async_add_entities(entities)
