"""
Integrate the Turn Touch smart home remote with Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/turn_touch/
"""

import logging
import threading
import time
import voluptuous as vol

from homeassistant.const import CONF_DEVICES, CONF_MAC
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['turntouch==0.4.3']

_LOGGER = logging.getLogger(__name__)

CONF_DEBOUNCE = 'debounce'

DOMAIN = 'turn_touch'
DATA_KEY = 'DATA_{component}'.format(component=DOMAIN)
DEFAULT_NAME = 'Turn Touch Remote'

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_DEBOUNCE, default=True): cv.boolean,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICES, default=[]): [DEVICE_SCHEMA],
    })
}, extra=vol.ALLOW_EXTRA)

EVENT_NAME = 'turntouch_press'
EVENT_DATA_ADDRESS = 'remote_address'
EVENT_DATA_ENTITY_ID = 'entity_id'
EVENT_DATA_NAME = 'remote_name'
EVENT_DATA_TYPE = 'press_type'

RETRY_DELAY = .25

TURN_TOUCH_PLATFORMS = ['sensor']


def setup(hass, config):
    """
    Set up the Turn Touch platform.

    Also, set up other components (eg. sensor) provided by this platform.
    """
    hass.data[DATA_KEY] = {'devices': {}}

    for device_config in config[DOMAIN][CONF_DEVICES]:
        turn_touch = TurnTouchRemote(hass, device_config)
        hass.data[DATA_KEY]['devices'][turn_touch.address] = turn_touch

    for platform in TURN_TOUCH_PLATFORMS:
        load_platform(hass, platform, DOMAIN, {}, config)

    return True


class TurnTouchRemote:
    """Representation of a Turn Touch remote.

    This does not inherit from the Entity class because Entities are created
    by platforms (e.g., sensor.turn_touch). But we must maintain one shared
    connection to the device, so that happens here.
    """

    def __init__(self, hass, config, listen=True):
        """Initialize the remote."""
        # pylint: disable=import-error
        import turntouch
        self._hass = hass
        self.address = config[CONF_MAC]
        self._debounce = config[CONF_DEBOUNCE]
        self._device = None

        class Handler(turntouch.DefaultActionHandler):
            """Callback handler for button presses."""

            def __init__(self, handler_func):
                self._handler_func = handler_func

            def action_any(self, action: turntouch.Action = None):
                """Handle all button presses."""
                if not action.is_off:
                    self._handler_func(action.name)

        self._handler = Handler(self._button_press)
        self.name = DEFAULT_NAME
        self._connect_lock = threading.Lock()
        threading.Thread(target=self._setup).start()

    def _setup(self):
        """Open the connection to the remote and start listening for events."""
        self._connect()
        self.get_name()
        self._listen()

    def get_name(self):
        """Read the device name."""
        # pylint: disable=import-error
        import turntouch
        delay = RETRY_DELAY
        while True:
            try:
                self.name = self._device.name
                return self.name
            except turntouch.TurnTouchException:
                _LOGGER.warning('Reading device name failed. Retrying...')
            except AttributeError:
                _LOGGER.warning('Cannot read name before connecting'
                                ' to the device. Retrying...')
            time.sleep(delay)
            delay *= 2
            self._connect()

    def get_battery(self):
        """Read the device battery level."""
        # pylint: disable=import-error
        import turntouch
        delay = RETRY_DELAY
        while True:
            try:
                return self._device.battery
            except turntouch.TurnTouchException:
                _LOGGER.warning('Reading device battery failed. Retrying...')
            except AttributeError:
                _LOGGER.warning('Cannot read battery level before connecting'
                                ' to the device. Retrying...')
            time.sleep(delay)
            delay *= 2
            self._connect()

    def _connect(self):
        """Connect to the Turn Touch remote. Retry on failure."""
        # pylint: disable=import-error
        import turntouch
        delay = RETRY_DELAY
        # pylint: disable=assignment-from-no-return
        got_lock = self._connect_lock.acquire(blocking=False)
        try:
            if not got_lock:
                # Another thread is already doing this. Let it finish & return.
                while not self._connect_lock.acquire():
                    pass
                return
            while True:
                if self._device:
                    self._device.disconnect()
                try:
                    self._device = turntouch.TurnTouch(
                        self.address, self._handler, self._debounce)
                    return True
                except turntouch.TurnTouchException:
                    _LOGGER.warning('Connecting failed. Retrying...')
                time.sleep(delay)
                delay *= 2
        finally:
            self._connect_lock.release()

    def _listen(self):
        """Listener for Turn Touch events.

        Automatically reconnect if the connection is dropped.
        """
        # pylint: disable=import-error
        import turntouch
        while True:
            try:
                self._device.listen_forever()
            except turntouch.TurnTouchException:
                _LOGGER.warning('Listening for events failed. Retrying...')
                self._connect()

    def _button_press(self, press_type):
        self._hass.bus.fire(EVENT_NAME, {
            EVENT_DATA_ADDRESS: self.address,
            EVENT_DATA_NAME: self.name,
            EVENT_DATA_TYPE: press_type,
        })
