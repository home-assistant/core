"""
homeassistant.components.media_player.firetv
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides control over an Amazon Fire TV (/stick) via
python-firetv, a Python 2.x module with a helper script
that exposes a HTTP server to fetch state and perform
actions.

Steps to configure your Amazon Fire TV stick with Home Assistant:

1. Turn on ADB Debugging on your Amazon Fire TV:
    a. From the main (Launcher) screen, select Settings.
    b. Select System > Developer Options.
    c. Select ADB Debugging.
2. Find Amazon Fire TV device IP:
    a. From the main (Launcher) screen, select Settings.
    b. Select System > About > Network.
3. `pip install firetv[firetv-server]` into a Python 2.x environment
4. `firetv-server -d <fire tv device IP>:5555`, background the process
5. Configure Home Assistant as follows:

media_player:
  platform: firetv
  # optional: where firetv-server is running (default is 'localhost:5556')
  host: localhost:5556
  # optional: device id (default is 'default')
  device: livingroom-firetv
  # optional: friendly name (default is 'Amazon Fire TV')
  name: My Amazon Fire TV

Note that python-firetv has support for multiple Amazon Fire TV devices.
If you have more than one configured, be sure to specify the device id used.
Run `firetv-server -h` and/or view the source for complete capabilities.

Possible states are:
 - off (TV screen is dark)
 - standby (standard UI is active - not apps)
 - idle (screen saver is active)
 - play (video is playing)
 - pause (video is paused)
 - disconnected (can't communicate with device)
"""

import requests

from homeassistant.const import (
    STATE_PLAYING, STATE_PAUSED, STATE_IDLE, STATE_OFF,
    STATE_UNKNOWN, STATE_STANDBY)

from homeassistant.components.media_player import (
    MediaPlayerDevice,
    SUPPORT_PAUSE, SUPPORT_VOLUME_SET,
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_NEXT_TRACK)

SUPPORT_FIRETV = SUPPORT_PAUSE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PREVIOUS_TRACK | \
    SUPPORT_NEXT_TRACK | SUPPORT_VOLUME_SET

DOMAIN = 'firetv'


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the firetv platform. """
    add_devices([
        FireTVDevice(
            config.get('host', 'localhost:5556'),
            config.get('device', 'default'),
            config.get('name', 'Amazon Fire TV')
        )
    ])


class FireTV(object):
    """ firetv-server client.

    Should a native Python 3 ADB module become available,
    python-firetv can support Python 3, it can be added
    as a dependency, and this class can be dispensed of.

    For now, it acts as a client to the firetv-server
    HTTP server (which must be running via Python 2).
    """

    DEVICE_STATE_URL = 'http://{0}/devices/state/{1}'
    DEVICE_ACTION_URL = 'http://{0}/devices/action/{1}/{2}'

    def __init__(self, host, device_id):
        self.host = host
        self.device_id = device_id

    @property
    def state(self):
        """ Get the device state.

        An exception means UNKNOWN state.
        """
        try:
            response = requests.get(
                FireTV.DEVICE_STATE_URL.format(
                    self.host,
                    self.device_id
                    )
                )
            return response.json()['state']
        except requests.exceptions.HTTPError:
            return STATE_UNKNOWN
        except requests.exceptions.RequestException:
            return STATE_UNKNOWN

    def action(self, action_id):
        """ Perform an action on the device.

        There is no action acknowledgment, so exceptions
        result in a pass.
        """
        try:
            requests.get(
                FireTV.DEVICE_ACTION_URL.format(
                    self.host,
                    self.device_id,
                    action_id
                    )
                )
        except requests.exceptions.HTTPError:
            pass
        except requests.exceptions.RequestException:
            pass


class FireTVDevice(MediaPlayerDevice):
    """ Represents an Amazon Fire TV device on the network. """

    def __init__(self, host, device, name):
        self._firetv = FireTV(host, device)
        self._name = name

    @property
    def name(self):
        """ Get the device name. """
        return self._name

    @property
    def should_poll(self):
        """ Device should be polled. """
        return True

    @property
    def supported_media_commands(self):
        """ Flags of media commands that are supported. """
        return SUPPORT_FIRETV

    @property
    def state(self):
        """ State of the player. """
        state_map = {
            'idle': STATE_IDLE,
            'off': STATE_OFF,
            'play': STATE_PLAYING,
            'pause': STATE_PAUSED,
            'standby': STATE_STANDBY,
            'disconnected': STATE_UNKNOWN,
        }
        return state_map.get(self._firetv.state, STATE_UNKNOWN)

    def turn_on(self):
        """ Turns on the device. """
        self._firetv.action('turn_on')

    def turn_off(self):
        """ Turns off the device. """
        self._firetv.action('turn_off')

    def media_play(self):
        """ Send play commmand. """
        self._firetv.action('media_play')

    def media_pause(self):
        """ Send pause command. """
        self._firetv.action('media_pause')

    def media_play_pause(self):
        """ Send play/pause command. """
        self._firetv.action('media_play_pause')

    def volume_up(self):
        """ Send volume up command. """
        self._firetv.action('volume_up')

    def volume_down(self):
        """ Send volume down command. """
        self._firetv.action('volume_down')

    def media_previous_track(self):
        """ Send previous track command (results in rewind). """
        self._firetv.action('media_previous')

    def media_next_track(self):
        """ Send next track command (results in fast-forward). """
        self._firetv.action('media_next')

    def media_seek(self, position):
        raise NotImplementedError()

    def mute_volume(self, mute):
        raise NotImplementedError()

    def play_youtube(self, media_id):
        raise NotImplementedError()

    def set_volume_level(self, volume):
        raise NotImplementedError()
