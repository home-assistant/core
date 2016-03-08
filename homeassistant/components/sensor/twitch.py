"""
Support for the Twitch stream status.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.twitch/
"""
from homeassistant.helpers.entity import Entity

STATE_STREAMING = 'streaming'
STATE_OFFLINE = 'offline'
ATTR_GAME = 'game'
ATTR_TITLE = 'title'
ICON = 'mdi:twitch'

REQUIREMENTS = ['python-twitch==1.2.0']
DOMAIN = 'twitch'


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Twitch platform."""
    add_devices(
        [TwitchSensor(channel) for channel in config.get('channels', [])])


class TwitchSensor(Entity):
    """Representation of an Twitch channel."""

    # pylint: disable=abstract-method
    def __init__(self, channel):
        """Initialize the sensor."""
        self._channel = channel
        self._state = STATE_OFFLINE
        self._preview = None
        self._game = None
        self._title = None
        self.update()

    @property
    def should_poll(self):
        """Device should be polled."""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._channel

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def entity_picture(self):
        """Return preview of current game."""
        return self._preview

    # pylint: disable=no-member
    def update(self):
        """Update device state."""
        from twitch.api import v3 as twitch
        stream = twitch.streams.by_channel(self._channel).get('stream')
        if stream:
            self._game = stream.get('channel').get('game')
            self._title = stream.get('channel').get('status')
            self._preview = stream.get('preview').get('small')
            self._state = STATE_STREAMING
        else:
            self._preview = None
            self._state = STATE_OFFLINE

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._state == STATE_STREAMING:
            return {
                ATTR_GAME: self._game,
                ATTR_TITLE: self._title,
            }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON
