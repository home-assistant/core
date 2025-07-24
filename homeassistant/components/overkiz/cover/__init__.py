"""Support for Overkiz covers - shutters etc."""

from pyoverkiz.enums import OverkizCommand, UIClass

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .. import OverkizDataConfigEntry
from .awning import Awning
from .generic_cover import OverkizGenericCover
from .vertical_cover import LowSpeedCover, VerticalCover


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Overkiz covers from a config entry."""
    data = entry.runtime_data

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
