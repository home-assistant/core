"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.core import HomeAssistant, callback

from . import (
    ATTR_ENTITY_PICTURE_LOCAL,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_SOUND_MODE_LIST,
)


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude static and token attributes from being recorded in the database."""
    return {
        ATTR_ENTITY_PICTURE_LOCAL,
        ATTR_ENTITY_PICTURE,
        ATTR_INPUT_SOURCE_LIST,
        ATTR_MEDIA_POSITION_UPDATED_AT,
        ATTR_MEDIA_POSITION,
        ATTR_SOUND_MODE_LIST,
    }
