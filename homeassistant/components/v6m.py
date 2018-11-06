"""Component to control v6m relays and sensors.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/v6m/
"""
import logging
import voluptuous as vol
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP, CONF_HOST, CONF_PORT, CONF_NAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyv6m==0.0.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'v6m'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DOMAIN): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, base_config):
    """Start V6M controller."""
    from pyv6m.pyv6m import V6M

    class V6MController(V6M):
        """Interface between HASS and V6M controller."""

        def __init__(self, host, port):
            """Host and port of the controller."""
            V6M.__init__(self, host, port, self.relay_callback,
                         self.sensor_callback)
            self._relay_subs = {}
            self._sensor_subs = {}

        def register_relay(self, device):
            """Add a device to subscribe to events."""
            self._register(self._relay_subs, device)

        def relay_callback(self, num, old_state, new_state):
            """Process relay states."""
            self._dispatch(self._relay_subs, num, new_state)

        def register_sensor(self, device):
            """Add a device to subscribe to events."""
            self._register(self._sensor_subs, device)

        def sensor_callback(self, num, old_state, new_state):
            """Process sensor states."""
            self._dispatch(self._sensor_subs, num, new_state)

        def _register(self, subs, device):
            if device.num not in subs:
                subs[device.num] = []
            subs[device.num].append(device)

        def _dispatch(self, subs, num, new_state):
            if num in subs:
                for sub in subs[num]:
                    if sub.callback(new_state):
                        sub.schedule_update_ha_state()

    config = base_config.get(DOMAIN)
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    controller = V6MController(host, port)
    hass.data[config[CONF_NAME]] = controller

    def cleanup(event):
        controller.close()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)
    return True


class V6MDevice():
    """Base class of a V6M device."""

    def __init__(self, controller, num, name):
        """Controller, address, and name of the device."""
        self._num = num
        self._name = name
        self._controller = controller

    @property
    def num(self):
        """Device number."""
        return self._num

    @property
    def name(self):
        """Device name."""
        return self._name

    @property
    def should_poll(self):
        """No need to poll."""
        return False
