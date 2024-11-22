"""Support for Nanoleaf event entity."""

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NanoleafConfigEntry, NanoleafCoordinator
from .const import TOUCH_MODELS
from .entity import NanoleafEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NanoleafConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Nanoleaf event."""
    coordinator = entry.runtime_data
    if coordinator.nanoleaf.model in TOUCH_MODELS:
        async_add_entities([NanoleafGestureEvent(coordinator)])


class NanoleafGestureEvent(NanoleafEntity, EventEntity):
    """Representation of a Nanoleaf event entity."""

    _attr_event_types = [
        "swipe_up",
        "swipe_down",
        "swipe_left",
        "swipe_right",
    ]
    _attr_translation_key = "touch"

    def __init__(self, coordinator: NanoleafCoordinator) -> None:
        """Initialize the Nanoleaf event entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._nanoleaf.serial_no}_gesture"

    async def async_added_to_hass(self) -> None:
        """Subscribe to Nanoleaf events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"nanoleaf_gesture_{self._nanoleaf.serial_no}",
                self._async_handle_event,
            )
        )

    @callback
    def _async_handle_event(self, gesture: str) -> None:
        """Handle the event."""
        self._trigger_event(gesture)
        self.async_write_ha_state()
