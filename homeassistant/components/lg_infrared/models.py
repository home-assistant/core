"""Models for the LG Infrared integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.components.select import SelectEntity

@dataclass
class LGIRRemoteData:
    """
    Shared state container for the LG IR Remote.
    
    This object is stored in hass.data and allows buttons and select 
    entities to stay in sync regarding the current tuner state.
    """
    # The source of truth for the tuner (DTV, BS, CS)
    current_tuner: str = "DTV"
    
    # Optional: store a reference to the select entity so buttons 
    # can trigger a UI refresh if the state changes via a button press.
    select_entity: SelectEntity | None = None

    def update_tuner(self, tuner: str) -> None:
        """Update the tuner state and refresh the UI entity if it exists."""
        self.current_tuner = tuner.upper()
        if self.select_entity:
            self.select_entity.async_write_ha_state()
