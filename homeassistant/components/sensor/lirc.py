"""
LIRC interface to receive signals from a infrared remote control.

This sensor will momentarily set state to various values as defined
in the .lintrc file which can be interpreted in home-assistant to
trigger various actions.

Sending signals to other IR receivers can be accomplished with the
shell_command component and the irsend command for now.
"""
# pylint: disable=import-error
import threading
import time
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

REQUIREMENTS = ['python-lirc>=1.2.1']
_LOGGER = logging.getLogger(__name__)
ICON = 'mdi:remote'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup LIRC capability."""
    # Perform safe import of third-party python-lirc module
    try:
        import lirc
    except ImportError:
        _LOGGER.error("You are missing a required dependency: python-lirc.")
        return False

    # blocking=True gives unexpected behavior (multiple responses for 1 press)
    lirc.init('home-assistant', blocking=False)
    sensor = LircSensor()
    add_devices([sensor])

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, sensor.stop)


class LircSensor(Entity):
    """Sensor entity for LIRC."""

    def __init__(self, *args, **kwargs):
        """Construct a LircSensor entity."""
        _LOGGER.info('Initializing LIRC sensor')
        Entity.__init__(self, *args, **kwargs)
        self.last_key_pressed = ''
        self._lirc_interface = LircInterface(self)
        self._lirc_interface.start()

    @property
    def name(self):
        """Name of lirc sensor."""
        return 'lirc'

    @property
    def state(self):
        """State of LIRC sensor."""
        return self.last_key_pressed

    def update_state(self, new_state):
        """Inform system of update when they occur."""
        self.last_key_pressed = new_state
        self.update_ha_state()

    def stop(self, _event):
        """Kill the helper thread on stop."""
        _LOGGER.info('Ending LIRC interface thread')
        self._lirc_interface.stopped.set()


class LircInterface(threading.Thread):
    """
    This interfaces with the lirc daemon to read IR commands.

    When using lirc in blocking mode, sometimes repeated commands get produced
    in the next read of a command so we use a thread here to just wait
    around until a non-empty response is obtained from lirc.
    """

    def __init__(self, parent):
        """Construct a LIRC interface object."""
        threading.Thread.__init__(self)
        self.stopped = threading.Event()
        self._parent = parent

    def run(self):
        """Main loop of LIRC interface thread."""
        import lirc
        while not self.stopped.isSet():
            code = lirc.nextcode()  # list; empty if no buttons pressed

            # interpret result from python-lirc
            if code:
                code = code[0]
            else:
                code = ''

            # update if changed.
            if code != self._parent.state:
                _LOGGER.info('Got new LIRC code %s', code)
                self._parent.update_state(code)
            else:
                time.sleep(0.1)  # avoid high CPU in this thread

        _LOGGER.info('LIRC interface thread stopped')
