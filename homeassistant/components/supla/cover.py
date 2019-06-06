"""Support for Supla cover - curtains, rollershutters etc."""
import logging
from pprint import pformat

from homeassistant.components.cover import ATTR_POSITION, CoverDevice
from homeassistant.components.supla import SuplaChannel

DEPENDENCIES = ['supla']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Supla covers."""
    if discovery_info is None:
        return

    _LOGGER.debug('Discovery: %s', pformat(discovery_info))

    add_entities([
        SuplaCover(device) for device in discovery_info
    ])


class SuplaCover(SuplaChannel, CoverDevice):
    """Representation of a Supla Cover."""

    @property
    def current_cover_position(self):
        """Return current position of cover. 0 is closed, 100 is open."""
        state = self.channel_data.get('state')
        if state:
            return 100 - state['shut']
        return None

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        self.action('REVEAL', percentage=kwargs.get(ATTR_POSITION))

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self.current_cover_position is None:
            return None
        return self.current_cover_position == 0

    def open_cover(self, **kwargs):
        """Open the cover."""
        self.action('REVEAL')

    def close_cover(self, **kwargs):
        """Close the cover."""
        self.action('SHUT')

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self.action('STOP')
