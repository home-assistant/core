"""Platform for UPB link integration."""

from typing import Any, override

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UpbConfigEntry
from .entity import UpbEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UpbConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the UPB link based on a config entry."""
    upb = config_entry.runtime_data
    unique_id = config_entry.entry_id
    async_add_entities(UpbLink(upb.links[link], unique_id, upb) for link in upb.links)


class UpbLink(UpbEntity, Scene):
    """Representation of a UPB Link."""

    def __init__(self, element, unique_id, upb):
        """Initialize the base of all UPB devices."""
        super().__init__(element, unique_id, upb)
        self._attr_name = element.name

    @override
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
