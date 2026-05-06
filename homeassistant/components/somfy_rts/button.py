"""Button platform for Somfy RTS."""

from rf_protocols import SomfyRTSButton

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import SomfyRTSConfigEntry, SomfyRTSEntity

PARALLEL_UPDATES = 1

# Somfy RTS PROG command requires 4 retransmit frames to reliably enter pairing mode.
_PROG_FRAME_REPEATS = 4


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SomfyRTSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Somfy RTS button platform."""
    async_add_entities([SomfyRTSProgButton(config_entry)])


class SomfyRTSProgButton(SomfyRTSEntity, ButtonEntity):
    """Button that sends the Somfy RTS PROG command to enter pairing mode."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "prog"

    def __init__(self, entry: SomfyRTSConfigEntry) -> None:
        """Initialize the PROG button."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_prog"

    async def async_press(self) -> None:
        """Send the PROG command."""
        await self._async_send_command(
            SomfyRTSButton.PROG, frame_repeats=_PROG_FRAME_REPEATS
        )
