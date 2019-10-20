"""Support for setting the Transmission BitTorrent client Turtle Mode."""
import logging

from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import ToggleEntity

from .const import DATA_TRANSMISSION, DATA_UPDATED, DOMAIN, SWITCH_TYPES

_LOGGING = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import config from configuration.yaml."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Transmission switch."""

    transmission_api = hass.data[DOMAIN][DATA_TRANSMISSION]
    name = config_entry.data[CONF_NAME]

    dev = []
    for switch_type, switch_name in SWITCH_TYPES.items():
        dev.append(TransmissionSwitch(switch_type, switch_name, transmission_api, name))

    async_add_entities(dev, True)


class TransmissionSwitch(ToggleEntity):
    """Representation of a Transmission switch."""

    def __init__(self, switch_type, switch_name, transmission_api, name):
        """Initialize the Transmission switch."""
        self._name = switch_name
        self.client_name = name
        self.type = switch_type
        self._transmission_api = transmission_api
        self._state = STATE_OFF
        self._data = None

    @property
    def name(self):
        """Return the name of the switch."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def should_poll(self):
        """Poll for status regularly."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._transmission_api.available

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if self.type == "on_off":
            _LOGGING.debug("Starting all torrents")
            self._transmission_api.start_torrents()
        elif self.type == "turtle_mode":
            _LOGGING.debug("Turning Turtle Mode of Transmission on")
            self._transmission_api.set_alt_speed_enabled(True)
        self._transmission_api.update()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self.type == "on_off":
            _LOGGING.debug("Stoping all torrents")
            self._transmission_api.stop_torrents()
        if self.type == "turtle_mode":
            _LOGGING.debug("Turning Turtle Mode of Transmission off")
            self._transmission_api.set_alt_speed_enabled(False)
        self._transmission_api.update()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    def update(self):
        """Get the latest data from Transmission and updates the state."""
        active = None
        if self.type == "on_off":
            self._data = self._transmission_api.data
            if self._data:
                active = self._data.activeTorrentCount > 0

        elif self.type == "turtle_mode":
            active = self._transmission_api.get_alt_speed_enabled()

        if active is None:
            return

        self._state = STATE_ON if active else STATE_OFF
