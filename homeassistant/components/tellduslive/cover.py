"""Support for Tellstick covers using Tellstick Net."""
import logging

from homeassistant.components import cover, tellduslive
from homeassistant.components.cover import CoverDevice
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .entry import TelldusLiveEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Old way of setting up TelldusLive.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up tellduslive sensors dynamically."""
    async def async_discover_cover(device_id):
        """Discover and add a discovered sensor."""
        client = hass.data[tellduslive.DOMAIN]
        async_add_entities([TelldusLiveCover(client, device_id)])

    async_dispatcher_connect(
        hass,
        tellduslive.TELLDUS_DISCOVERY_NEW.format(cover.DOMAIN,
                                                 tellduslive.DOMAIN),
        async_discover_cover,
    )


class TelldusLiveCover(TelldusLiveEntity, CoverDevice):
    """Representation of a cover."""

    @property
    def is_closed(self):
        """Return the current position of the cover."""
        return self.device.is_down

    def close_cover(self, **kwargs):
        """Close the cover."""
        self.device.down()
        self._update_callback()

    def open_cover(self, **kwargs):
        """Open the cover."""
        self.device.up()
        self._update_callback()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self.device.stop()
        self._update_callback()
