"""
Support for feedreader sensors.

For more details about this platform, please refer to the documentation at
at https://home-assistant.io/components/sensor.feedreader/
"""
import logging

from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['feedreader']

DOMAIN = 'feedreader'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up feedreader sensors."""
    for url in discovery_info:
        adding = "Adding feedreader sensor for " + url
        logging.getLogger(__name__).info(adding)
        add_devices([FeedreaderSensor(hass, url)])


class FeedreaderSensor(Entity):
    """Representation of a feedreader sensor."""

    def __init__(self, hass, url):
        """Initialize the sensor."""
        self.hass = hass
        self._url = url
        self._state = None
        self.update()

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return the ID of the sensor."""
        return '{}.{}'.format(self.__class__, self.name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._url.split("/")[2].replace(".", "_")

    def update(self):
        """Update state of the device."""
        self._state = self.hass.data[DOMAIN][self._url]['title']

    @property
    def should_poll(self):
        """Poll the feed."""
        return True

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        feed = self.hass.data[DOMAIN][self._url]
        published = feed.get('published')
        updated = feed.get('updated')
        link = feed.get('link')
        feed_id = feed.get('id')
        content = feed.get('content')
        attributes = {"published": published,
                      "updated": updated,
                      "link": link,
                      "id": feed_id,
                      "content": content}
        return attributes
