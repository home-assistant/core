"""Platform for UPB link integration."""
from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UpbEntity
from .const import DOMAIN, UPB_BLINK_RATE_SCHEMA, UPB_BRIGHTNESS_RATE_SCHEMA

SERVICE_LINK_DEACTIVATE = "link_deactivate"
SERVICE_LINK_FADE_STOP = "link_fade_stop"
SERVICE_LINK_GOTO = "link_goto"
SERVICE_LINK_FADE_START = "link_fade_start"
SERVICE_LINK_BLINK = "link_blink"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UPB link based on a config entry."""
    upb = hass.data[DOMAIN][config_entry.entry_id]["upb"]
    unique_id = config_entry.entry_id
    async_add_entities(UpbLink(upb.links[link], unique_id, upb) for link in upb.links)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_LINK_DEACTIVATE, {}, "async_link_deactivate"
    )
    platform.async_register_entity_service(
        SERVICE_LINK_FADE_STOP, {}, "async_link_fade_stop"
    )
    platform.async_register_entity_service(
        SERVICE_LINK_GOTO, UPB_BRIGHTNESS_RATE_SCHEMA, "async_link_goto"
    )
    platform.async_register_entity_service(
        SERVICE_LINK_FADE_START, UPB_BRIGHTNESS_RATE_SCHEMA, "async_link_fade_start"
    )
    platform.async_register_entity_service(
        SERVICE_LINK_BLINK, UPB_BLINK_RATE_SCHEMA, "async_link_blink"
    )


class UpbLink(UpbEntity, Scene):
    """Representation of an UPB Link."""

    def __init__(self, element, unique_id, upb):
        """Initialize the base of all UPB devices."""
        super().__init__(element, unique_id, upb)
        self._attr_name = element.name

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the task."""
        self._element.activate()

    async def async_link_deactivate(self):
        """Activate the task."""
        self._element.deactivate()

    async def async_link_goto(self, rate, brightness=None, brightness_pct=None):
        """Activate the task."""
        if brightness is not None:
            brightness_pct = round(brightness / 2.55)
        self._element.goto(brightness_pct, rate)

    async def async_link_fade_start(self, rate, brightness=None, brightness_pct=None):
        """Start dimming a link."""
        if brightness is not None:
            brightness_pct = round(brightness / 2.55)
        self._element.fade_start(brightness_pct, rate)

    async def async_link_fade_stop(self):
        """Stop dimming a link."""
        self._element.fade_stop()

    async def async_link_blink(self, blink_rate):
        """Blink a link."""
        blink_rate = int(blink_rate * 60)
        self._element.blink(blink_rate)
