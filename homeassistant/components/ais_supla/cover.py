"""Support for Supla cover - curtains, rollershutters etc."""
from datetime import timedelta
import logging

from homeassistant.components.ais_supla import SuplaChannel
from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_GARAGE,
    CoverDevice,
)

from .const import CONF_CHANNELS, CONF_SERVER, DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)
SUPLA_SHUTTER = "CONTROLLINGTHEROLLERSHUTTER"
SUPLA_GATE = "CONTROLLINGTHEGATE"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an SUPLA switch based on existing config."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    server = hass.data[DOMAIN][CONF_SERVER][config_entry.entry_id]
    channels = hass.data[DOMAIN][CONF_CHANNELS]["cover"]
    scan_interval_in_sec = 60
    if "scan_interval" in config_entry.data:
        scan_interval_in_sec = config_entry.data["scan_interval"]
    for device in channels:
        device_name = device["function"]["name"]
        if device_name == SUPLA_SHUTTER:
            async_add_entities([SuplaCover(device, server, scan_interval_in_sec)])
        elif device_name == SUPLA_GATE:
            async_add_entities([SuplaGateDoor(device, server, scan_interval_in_sec)])


class SuplaCover(SuplaChannel, CoverDevice):
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


class SuplaGateDoor(SuplaChannel, CoverDevice):
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
