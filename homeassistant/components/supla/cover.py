"""Support for Supla cover - curtains, rollershutters, entry gate etc."""
import logging
from pprint import pformat

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_GARAGE,
    CoverEntity,
)
from homeassistant.components.supla import SuplaChannel

_LOGGER = logging.getLogger(__name__)

SUPLA_SHUTTER = "CONTROLLINGTHEROLLERSHUTTER"
SUPLA_GATE = "CONTROLLINGTHEGATE"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Supla covers."""
    if discovery_info is None:
        return

    _LOGGER.debug("Discovery: %s", pformat(discovery_info))

    entities = []
    for device in discovery_info:
        device_name = device["function"]["name"]
        if device_name == SUPLA_SHUTTER:
            entities.append(SuplaCover(device))
        elif device_name == SUPLA_GATE:
            entities.append(SuplaGateDoor(device))
    add_entities(entities)


class SuplaCover(SuplaChannel, CoverEntity):
    """Representation of a Supla Cover."""

    @property
    def current_cover_position(self):
        """Return current position of cover. 0 is closed, 100 is open."""
        state = self.channel_data.get("state")
        if state:
            return 100 - state["shut"]
        return None

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        self.action("REVEAL", percentage=kwargs.get(ATTR_POSITION))

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self.current_cover_position is None:
            return None
        return self.current_cover_position == 0

    def open_cover(self, **kwargs):
        """Open the cover."""
        self.action("REVEAL")

    def close_cover(self, **kwargs):
        """Close the cover."""
        self.action("SHUT")

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self.action("STOP")


class SuplaGateDoor(SuplaChannel, CoverEntity):
    """Representation of a Supla gate door."""

    @property
    def is_closed(self):
        """Return if the gate is closed or not."""
        state = self.channel_data.get("state")
        if state and "hi" in state:
            return state.get("hi")
        return None

    def open_cover(self, **kwargs) -> None:
        """Open the gate."""
        if self.is_closed:
            self.action("OPEN_CLOSE")

    def close_cover(self, **kwargs) -> None:
        """Close the gate."""
        if not self.is_closed:
            self.action("OPEN_CLOSE")

    def stop_cover(self, **kwargs) -> None:
        """Stop the gate."""
        self.action("OPEN_CLOSE")

    def toggle(self, **kwargs) -> None:
        """Toggle the gate."""
        self.action("OPEN_CLOSE")

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_GARAGE
