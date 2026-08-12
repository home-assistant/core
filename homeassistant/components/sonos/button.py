"""Button entities for Sonos."""

from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SONOS_CREATE_BUTTON
from .entity import SonosEntity
from .helpers import SonosConfigEntry
from .speaker import SonosSpeaker


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SonosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sonos button entities from a config entry."""

    @callback
    def async_create_entities(speaker: SonosSpeaker) -> None:
        """Handle device discovery and create button entities."""
        async_add_entities([SonosCancelAnnouncementButton(speaker, config_entry)])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_BUTTON, async_create_entities)
    )


class SonosCancelAnnouncementButton(SonosEntity, ButtonEntity):
    """Button to cancel the current Sonos announcement."""

    _attr_translation_key = "cancel_announcement"

    def __init__(self, speaker: SonosSpeaker, config_entry: SonosConfigEntry) -> None:
        """Initialize the cancel announcement button."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-cancel_announcement"

    @override
    async def _async_fallback_poll(self) -> None:
        """No-op: button state does not need polling."""

    @override
    async def async_press(self) -> None:
        """Cancel the current announcement audio clip."""
        await self.speaker.async_cancel_announcement()
