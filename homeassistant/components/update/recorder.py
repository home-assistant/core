"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.core import HomeAssistant, callback

from .const import ATTR_IN_PROGRESS, ATTR_RELEASE_SUMMARY


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude large and chatty update attributes from being recorded in the database."""
    return {ATTR_ENTITY_PICTURE, ATTR_IN_PROGRESS, ATTR_RELEASE_SUMMARY}
