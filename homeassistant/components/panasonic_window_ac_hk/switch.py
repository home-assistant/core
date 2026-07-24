"""Switch platform for the Panasonic Window A/C (Hong Kong/Macau).

Exposes the nanoeX feature, which lives inside the full state frame, so toggling
it re-asserts the current mode, temperature, fan and swing.
"""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import PanasonicWindowAcHKConfigEntry
from .entity import PanasonicWindowAcHKEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PanasonicWindowAcHKConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the nanoeX switch for one air conditioner."""
    async_add_entities([PanasonicWindowAcHKNanoexSwitch(entry)])


class PanasonicWindowAcHKNanoexSwitch(
    PanasonicWindowAcHKEntity, SwitchEntity, RestoreEntity
):
    """Toggle nanoeX by re-sending the full state frame."""

    _attr_translation_key = "nanoex"
    _attr_assumed_state = True

    def __init__(self, entry: PanasonicWindowAcHKConfigEntry) -> None:
        """Initialize the nanoeX switch."""
        super().__init__(entry, "nanoex")

    async def async_added_to_hass(self) -> None:
        """Restore the last assumed nanoeX state across restarts."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in (STATE_ON, STATE_OFF):
            self._runtime_data.nanoex = last_state.state == STATE_ON

    @property
    def is_on(self) -> bool:
        """Return whether nanoeX is currently assumed on."""
        return self._runtime_data.nanoex

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable nanoeX (re-sends the full state frame)."""
        self._runtime_data.nanoex = True
        await self._async_send_full()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable nanoeX (re-sends the full state frame)."""
        self._runtime_data.nanoex = False
        await self._async_send_full()
        self.async_write_ha_state()
