"""
Support for Harmony Hub devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/remote.harmony/

Sample configuation.yaml entry:
remote:
  - platform: harmony
    name: Bedroom
    username: !secret username   (email addresse used to login to harmony website)
    password: !secret password   (password used to login to harmony website)
    host: 10.168.1.13            (Harmony device IP address)
    port: 5222                   (Harmony device port, 5222 is default)
    activity: BedroomTV          (activity to start if no activity is specified when turnon service is called, Optional)
  - platform: harmony
    name: Family Room
    username: !secret username
    password: !secret password
    host: 10.168.1.16
    port: 5222
    activity: Kodi

Configuration File
  Upon startup one file will be written to your HASS configuration directory per device in the following format:
    harmony_conf_REMOTENAME.txt.  The file will contain:
        A list of all programmed activity names and ID numbers
        A list of all programmed device names and ID numbers
        A list of all available commands per programmed device

Template sensors can be utilized to display current activity in the frontend by adding the following:
sensor:
  - platform: template
    sensors:
      family_room:
        value_template: '{{ states.remote.family_room.attributes.current_activity }}'
        friendly_name: 'Family Room'
      bedroom:
        value_template: '{{ states.remote.bedroom.attributes.current_activity }}'
        friendly_name: 'bedroom'

The remote's current activity can be utilized in automations as shown below.
    The example will turn on an input boolean switch on when the remote's state changes and the Kodi activity is started
    The second rule will turn off the same switch when the current activity is changed to PowerOff

automation:
- alias: "Watch TV started from harmony hub"
  trigger:
    platform: state
    entity_id: remote.family_room
  condition:
    condition: template
    value_template: '{{ trigger.to_state.attributes.current_activity == "Kodi" }}'
  action:
    service: input_boolean.turn_on
    entity_id: input_boolean.notify

- alias: "PowerOff started from harmony hub"
  trigger:
    platform: state
    entity_id: remote.family_room
  condition:
    condition: template
    value_template: '{{ trigger.to_state.attributes.current_activity == "PowerOff" }}'
  action:
    service: input_boolean.turn_off
    entity_id: input_boolean.notify

Supported services
  Turn Off:
    Turn off all devices that were switched on from the start of the current activity
  Turn On:
    Start an activity, will start the default activity from configuration.yaml if no activity is specified.
    The specified activity can either be the activity name or the activity ID from the configuration file written to
      your HASS config directory.  The service will respond faster if the activity ID is passed instead of the name
  Send Command:
    Send a command to one device, device ID and available commands are written to the configuration file at startup
  Sync:
    Syncs the Harmony device with the Harmony web service if any changes are made from the web portal or app

"""

from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON
import homeassistant.components.remote as remote
import pyharmony
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.remote import PLATFORM_SCHEMA

REQUIREMENTS = ['pyharmony>=1.0.7']
_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = 'device'
ATTR_COMMAND = 'command'
ATTR_ACTIVITY = 'activity'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.string,
    vol.Optional(ATTR_ACTIVITY, default='Not_Set'): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):

    harmony_conf_file = hass.config.path('harmony_conf_' + config.get(CONF_NAME) + '.txt')
    pyharmony.ha_get_config_file(config.get(CONF_USERNAME),
                                 config.get(CONF_PASSWORD),
                                 config.get(CONF_HOST),
                                 config.get(CONF_PORT),
                                 harmony_conf_file)

    add_devices([HarmonyRemote(config.get(CONF_NAME),
                               config.get(CONF_USERNAME),
                               config.get(CONF_PASSWORD),
                               config.get(CONF_HOST),
                               config.get(CONF_PORT),
                               config.get(ATTR_ACTIVITY))])
    return True


class HarmonyRemote(remote.RemoteDevice):
    """Remote representation used expose services to control a Harmony device"""

    def __init__(self, name, username, password, host, port, activity):
        self._name = name
        self._email = username
        self._password = password
        self._ip = host
        self._port = port
        self._state = None
        self._current_activity = None
        self._default_activity = activity


    @property
    def name(self):
        """Return the Harmony device's name"""
        return self._name


    @property
    def state(self):
        """Return the state of the Harmony device."""
        return self._state


    @property
    def state_attributes(self):
        """Overwrite inherited attributes"""
        return {'current_activity': self._current_activity}


    def is_on(self):
        """Return False if PowerOff is the current activity, otherwise true."""
        return self.update()


    def update(self):
        """Return current activity"""
        state = pyharmony.ha_get_current_activity(self._email,
                                    self._password,
                                    self._ip,
                                    self._port)
        self._current_activity = state
        if state  != 'PowerOff':
            self._state = STATE_ON
        else:
            self._state = STATE_OFF


    def turn_on(self, **kwargs):
        """Start an activity from the Harmony device"""
        if not kwargs[ATTR_ACTIVITY]:
            activity = self._default_activity
        else:
            activity = kwargs[ATTR_ACTIVITY]
        pyharmony.ha_start_activity(self._email,
                                    self._password,
                                    self._ip,
                                    self._port,
                                    activity)


    def turn_off(self):
        """Start the PowerOff activity"""
        pyharmony.ha_power_off(self._email,
                                    self._password,
                                    self._ip,
                                    self._port)


    def send_command(self, **kwargs):
        """Send a command to one device"""
        pyharmony.ha_send_command(self._email,
                                    self._password,
                                    self._ip,
                                    self._port,
                                  kwargs[ATTR_DEVICE],
                                  kwargs[ATTR_COMMAND])


    def sync(self):
        """Sync the Harmony device with the web service"""
        pyharmony.ha_sync(self._harmony_device._email,
                               self._harmony_device._password,
                               self._harmony_device._ip,
                               self._harmony_device._port)