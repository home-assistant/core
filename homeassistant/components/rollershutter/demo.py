"""
Demo platform for the rollor shutter component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.rollershutter import RollershutterDevice
from homeassistant.const import EVENT_TIME_CHANGED
from homeassistant.helpers.event import track_utc_time_change


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Demo roller shutters."""
    add_devices([
        DemoRollershutter(hass, 'Kitchen Window', 0),
        DemoRollershutter(hass, 'Living Room Window', 100),
    ])


class DemoRollershutter(RollershutterDevice):
    """Representation of a demo roller shutter."""

    # pylint: disable=no-self-use
    def __init__(self, hass, name, position):
        """Initialize the roller shutter."""
        self.hass = hass
        self._name = name
        self._position = position
        self._moving_up = True
        self._listener = None

    @property
    def name(self):
        """Return the name of the roller shutter."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed for a demo roller shutter."""
        return False

    @property
    def current_position(self):
        """Return the current position of the roller shutter."""
        return self._position

    def move_up(self, **kwargs):
        """Move the roller shutter down."""
        if self._position == 0:
            return

        self._listen()
        self._moving_up = True

    def move_down(self, **kwargs):
        """Move the roller shutter up."""
        if self._position == 100:
            return

        self._listen()
        self._moving_up = False

    def stop(self, **kwargs):
        """Stop the roller shutter."""
        if self._listener is not None:
            self.hass.bus.remove_listener(EVENT_TIME_CHANGED, self._listener)
            self._listener = None

    def _listen(self):
        """Listen for changes."""
        if self._listener is None:
            self._listener = track_utc_time_change(self.hass,
                                                   self._time_changed)

    def _time_changed(self, now):
        """Track time changes."""
        if self._moving_up:
            self._position -= 10
        else:
            self._position += 10

        if self._position % 100 == 0:
            self.stop()

        self.update_ha_state()
