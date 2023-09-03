"""Support for Overkiz covers - shutters etc."""
from pyoverkiz.enums import OverkizCommand, UIClass
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .const import DOMAIN
from .cover_entities.awning import Awning
from .cover_entities.generic_cover import OverkizGenericCover
from .cover_entities.vertical_cover import LowSpeedCover, VerticalCover

SERVICE_SET_COVER_POSITION = "set_cover_position_and_tilt"


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

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_COVER_POSITION,
        {
            vol.Required(ATTR_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Required(ATTR_TILT_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
        },
        "async_set_cover_position_and_tilt",
        [CoverEntityFeature.SET_POSITION, CoverEntityFeature.SET_TILT_POSITION],
    )
