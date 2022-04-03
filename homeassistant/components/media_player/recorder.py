"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.core import HomeAssistant, callback

from . import ATTR_INPUT_SOURCE_LIST, ATTR_SOUND_MODE_LIST


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude static and token attributes from being recorded in the database."""
    return {ATTR_SOUND_MODE_LIST, ATTR_ENTITY_PICTURE, ATTR_INPUT_SOURCE_LIST}
