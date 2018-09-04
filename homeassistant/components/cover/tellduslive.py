"""
Support for Tellstick covers using Tellstick Net.

This platform uses the Telldus Live online service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.tellduslive/
"""
import logging

from homeassistant.components.cover import CoverDevice
from homeassistant.components.tellduslive import TelldusLiveEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Telldus Live covers."""
    if discovery_info is None:
        return

    add_entities(TelldusLiveCover(hass, cover) for cover in discovery_info)


class TelldusLiveCover(TelldusLiveEntity, CoverDevice):
    """Representation of a cover."""

    @property
    def is_closed(self):
        """Return the current position of the cover."""
        return self.device.is_down

    def close_cover(self, **kwargs):
        """Close the cover."""
        self.device.down()
        self.changed()

    def open_cover(self, **kwargs):
        """Open the cover."""
        self.device.up()
        self.changed()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self.device.stop()
        self.changed()
