"""
homeassistant.components.rollershutter.command_rollershutter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a command rollershutter.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/rollershutter.command_rollershutter/
"""
import logging
import subprocess

from homeassistant.components.rollershutter import RollershutterDevice
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.util import template

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Command Rollershutter"


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return rollershutter controlled by shell commands. """

    devices = config.get('rollershutters', {})
    rollershutters = []
#    logger = logging.getLogger(__name__)

    for dev_name, properties in devices.items():
        rollershutters.append(
            CommandRollershutter(
                hass,
                properties.get('name', dev_name),
                properties.get('upcmd', 'true'),
                properties.get('downcmd', 'true'),
                properties.get('stopcmd', 'true'),
                properties.get('statecmd', 'true'),
                properties.get(CONF_VALUE_TEMPLATE, False)))

    add_devices_callback(rollershutters)


# pylint: disable=too-many-arguments, too-many-instance-attributes
class CommandRollershutter(RollershutterDevice):
    """ Represents a rollershutter -  can be controlled using shell cmd. """

    # pylint: disable=too-many-arguments
    def __init__(self, hass, name, command_up, command_down, command_stop,
                 command_state, value_template):

        self._hass = hass
        self._name = name
        self._state = 0  # False
        self._command_up = command_up
        self._command_down = command_down
        self._command_stop = command_stop
        self._command_state = command_state
        self._value_template = value_template

    @staticmethod
    def _rollershutter(command):
        """ Execute the actual commands. """
        _LOGGER.info('Running command: %s', command)

        success = (subprocess.call(command, shell=True) == 0)

        if not success:
            _LOGGER.error('Command failed: %s', command)

        return success

    @staticmethod
    def _query_state_value(command):
        """ Execute state command for return value. """
        _LOGGER.info('Running state command: %s', command)

        try:
            return_value = subprocess.check_output(command, shell=True)
            return return_value.strip().decode('utf-8')
        except subprocess.CalledProcessError:
            _LOGGER.error('Command failed: %s', command)

    @staticmethod
    def _query_state_code(command):
        """ Execute state command for return code. """
        _LOGGER.info('Running state command: %s', command)
        return subprocess.call(command, shell=True) == 0

    @property
    def should_poll(self):
        """ Only poll if we have statecmd. """
        return self._command_state is not None
#        return False

    @property
    def name(self):
        """ The name of the rollershutter. """
        return self._name

    @property
    def current_position(self):
        """
        Return current position of rollershutter.
        None is unknown, 0 is closed, 100 is fully open.
        """
#        return None
        return self._state

    def _query_state(self):
        """ Query for state. """
        if not self._command_state:
            _LOGGER.error('No state command specified')
            return
        if self._value_template:
            return CommandRollershutter._query_state_value(self._command_state)
        return CommandRollershutter._query_state_code(self._command_state)

    def update(self):
        """ Update device state. """
        if self._command_state:
            payload = str(self._query_state())
            if self._value_template:
                payload = template.render_with_possible_json_value(
                    # self._hass, self._value_template, payload, 'Unknown')
                    self._hass, self._value_template, payload)
            self._state = int(payload)
            # self._state = (payload.lower() == "true")

    def move_up(self, **kwargs):
        """ Move the rollershutter up. """
        if (CommandRollershutter._rollershutter(self._command_up) and
                not self._command_state):
            self._state = True  # Up
            self.update_ha_state()

    def move_down(self, **kwargs):
        """ Move the rollershutter down. """
        if (CommandRollershutter._rollershutter(self._command_down) and
                not self._command_state):
            self._state = True  # Down
            self.update_ha_state()

    def stop(self, **kwargs):
        """ Stop the device. """
        if (CommandRollershutter._rollershutter(self._command_stop) and
                not self._command_state):
            self._state = False  # Stop
            self.update_ha_state()
