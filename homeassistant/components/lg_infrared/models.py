"""Models for the LG Infrared integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import tuner_signal

class LGIRRemoteData:
    """Handle shared state for LG IR Remote."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.entry_id = entry_id
        self.current_tuner: str = "DTV"

    def update_tuner(self, tuner: str) -> None:
        """Update tuner state and notify listeners."""
        normalized_tuner = tuner.upper()
        
        if self.current_tuner == normalized_tuner:
            return
            
        self.current_tuner = normalized_tuner
        
        # Fire the signal using our helper
        async_dispatcher_send(self.hass, tuner_signal(self.entry_id))
        
