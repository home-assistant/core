"""Describe the logbook events of Hikvision."""

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Event, HomeAssistant, callback

from .const import ATTR_MESSAGE, ATTR_NAME, DOMAIN, EVENT_IMAGE_SETTING_CHANGED


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, Any]]], None],
) -> None:
    """Describe the logbook events of Hikvision."""

    @callback
    def async_describe_image_setting_changed(event: Event) -> dict[str, Any]:
        """Describe a setting the camera changed on its own, or applies later."""
        data = event.data
        description = {
            LOGBOOK_ENTRY_NAME: data[ATTR_NAME],
            LOGBOOK_ENTRY_MESSAGE: data[ATTR_MESSAGE],
        }
        if entity_id := data.get(ATTR_ENTITY_ID):
            description[LOGBOOK_ENTRY_ENTITY_ID] = entity_id
        return description

    async_describe_event(
        DOMAIN, EVENT_IMAGE_SETTING_CHANGED, async_describe_image_setting_changed
    )
