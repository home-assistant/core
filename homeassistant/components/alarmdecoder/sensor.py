"""Support for AlarmDecoder sensors (Shows Panel Display)."""
import logging

from homeassistant.helpers.entity import Entity

from . import SIGNAL_PANEL_MESSAGE

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up for AlarmDecoder sensor devices."""
    _LOGGER.debug("AlarmDecoderSensor: setup_platform")

    device = AlarmDecoderSensor(hass)

    add_entities([device])


class AlarmDecoderSensor(Entity):
    """Representation of an AlarmDecoder keypad."""

    def __init__(self, hass):
        """Initialize the alarm panel."""
        self._display = ""
        self._state = None
        self._icon = "mdi:alarm-check"
        self._name = "Alarm Panel Display"

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_PANEL_MESSAGE, self._message_callback
            )
        )

    def _message_callback(self, message):
        if self._display != message.text:
            self._display = message.text
            self.schedule_update_ha_state()

    @property
    def icon(self):
        """Return the icon if any."""
        return self._icon

    @property
    def state(self):
        """Return the overall state."""
        return self._display

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False
