# flake8: noqa
"""
Support for interface with an Sony Bravia TV.

By Antonio Parraga Navarro

dedicated to Isabel

"""
import logging
import os
import base64
import json
import socket
import struct
import re
from subprocess import Popen, PIPE
from io import StringIO
import requests
from homeassistant.loader import get_component


from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON)

BRAVIA_CONFIG_FILE = 'bravia.conf'
CLIENTID_PREFIX = 'HomeAssistant'
NICKNAME = 'Home Assistant'
TIMEOUT = 10

# Map ip to request id for configuring
_CONFIGURING = {}

_LOGGER = logging.getLogger(__name__)


SUPPORT_BRAVIA = SUPPORT_PAUSE | SUPPORT_VOLUME_STEP | \
                 SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | SUPPORT_PREVIOUS_TRACK | \
                 SUPPORT_NEXT_TRACK | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE


def _config_from_file(filename, config=None):
    """Small configuration file management function."""
    if config:
        # We're writing configuration
        bravia_config = _config_from_file(filename)
        if bravia_config is None:
            bravia_config = {}
        new_config = bravia_config.copy()
        new_config.update(config)
        try:
            with open(filename, 'w') as fdesc:
                string_io = StringIO()
                json.dump(new_config, string_io)
                fdesc.write(string_io.getvalue())
        except IOError as error:
            _LOGGER.error('Saving config file failed: %s', error)
            return False
        return True
    else:
        # We're reading config
        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as fdesc:
                    return json.loads(fdesc.read())
            except ValueError as error:
                return {}
            except IOError as error:
                _LOGGER.error('Reading config file failed: %s', error)
                # This won't work yet
                return False
        else:
            return {}


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the Sony Bravia TV platform."""
    host = config.get(CONF_HOST)

    if host is None:
        return  # if no host configured, do not continue

    pin = None
    bravia_config = _config_from_file(hass.config.path(BRAVIA_CONFIG_FILE))
    while len(bravia_config):
        # Setup a configured PlexServer
        host_ip, host_config = bravia_config.popitem()
        if host_ip == host:
            pin = host_config['pin']
            mac = host_config['mac']
            name = config.get(CONF_NAME)
            add_devices_callback([BraviaTVDevice(host, mac, name, pin)])
            return

    setup_bravia(config, pin, hass, add_devices_callback)


# pylint: disable=too-many-branches
def setup_bravia(config, pin, hass, add_devices_callback):
    """Setup a sony bravia based on host parameter."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    if name is None:
        name = "Sony Bravia TV"

    if pin is None:
        request_configuration(config, hass, add_devices_callback)
        return
    else:
        mac = _get_mac_address(host)
        if mac is not None:
            mac = mac.decode('utf8')
        # If we came here and configuring this host, mark as done
        if host in _CONFIGURING:
            request_id = _CONFIGURING.pop(host)
            configurator = get_component('configurator')
            configurator.request_done(request_id)
            _LOGGER.info('Discovery configuration done!')

        # Save config
        if not _config_from_file(
                hass.config.path(BRAVIA_CONFIG_FILE),
                {host: {'pin': pin, 'mac': mac}}):
            _LOGGER.error('failed to save config file')

        add_devices_callback([BraviaTVDevice(host, mac, name, pin)])


def request_configuration(config, hass, add_devices_callback):
    """Request configuration steps from the user."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    if name is None:
        name = "Sony Bravia"

    configurator = get_component('configurator')

    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[host], "Failed to register, please try again.")
        return

    def bravia_configuration_callback(data):
        """Callback after user enter PIN."""
        pin = data.get('pin')
        cookie = _bravia_auth(host, pin)
        if not cookie:
            request_configuration(config, hass, add_devices_callback)
        else:
            setup_bravia(config, pin, hass, add_devices_callback)

    _CONFIGURING[host] = configurator.request_config(
        hass, name, bravia_configuration_callback,
        description='Enter the Pin shown on your Sony Bravia TV.' +
        'If no Pin is shown, enter 0000 to let TV show you a Pin.',
        description_image="/static/images/smart-tv.png",
        submit_caption="Confirm",
        fields=[{'id': 'pin', 'name': 'Enter the pin', 'type': ''}]
    )


def _jdata_build(method, params):
    if params:
        ret = json.dumps({"method": method, "params": [params], "id": 1, "version": "1.0"})
    else:
        ret = json.dumps({"method": method, "params": [], "id": 1, "version": "1.0"})
    return ret


def _wakeonlan(ethernet_address):
    addr_byte = ethernet_address.split(':')
    hw_addr = struct.pack('BBBBBB', int(addr_byte[0], 16),
                          int(addr_byte[1], 16),
                          int(addr_byte[2], 16),
                          int(addr_byte[3], 16),
                          int(addr_byte[4], 16),
                          int(addr_byte[5], 16))
    msg = b'\xff' * 6 + hw_addr * 16
    socket_instance = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    socket_instance.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    socket_instance.sendto(msg, ('<broadcast>', 9))
    socket_instance.close()


def _bravia_auth(ip_address, pin):

    authorization = json.dumps(
        {"method": "actRegister",
         "params": [{"clientid": CLIENTID_PREFIX,
                     "nickname": NICKNAME,
                     "level": "private"},
                    [{"value": "yes",
                      "function": "WOL"}]],
         "id": 1,
         "version": "1.0"}
    ).encode('utf-8')

    headers = {}
    if pin:
        username = ''
        base64string = base64.encodebytes(('%s:%s' % (username, pin)).encode())\
            .decode().replace('\n', '')
        headers['Authorization'] = "Basic %s" % base64string
        headers['Connection'] = "keep-alive"

    try:
        response = requests.post('http://'+ip_address+'/sony/accessControl',
                                 data=authorization, headers=headers, timeout=TIMEOUT)

    except requests.exceptions.HTTPError as exception_instance:
        _LOGGER.error("[W] HTTPError: " + str(exception_instance))
        return None

    except Exception as exception_instance:  # pylint: disable=broad-except
        _LOGGER.error("[W] Exception: " + str(exception_instance))
        return None

    else:
        _LOGGER.info(json.dumps(response.json(), indent=4))
        return response.cookies

    return None


def _get_mac_address(ip_address):
    pid = Popen(["arp", "-n", ip_address], stdout=PIPE)
    pid_component = pid.communicate()[0]
    mac = re.search(r"(([a-f\d]{1,2}\:){5}[a-f\d]{1,2})".encode('UTF-8'), pid_component).groups()[0]
    return mac


# pylint: disable=abstract-method, too-many-public-methods, too-many-instance-attributes, too-many-arguments
class BraviaTVDevice(MediaPlayerDevice):
    """Representation of a Sony Bravia TV."""

    def __init__(self, host, mac, name, pin):
        """Initialize the sony bravia device."""
        self._host = host
        self._name = name
        self._mac = mac
        self._pin = pin
        self._muted = False
        self._program_name = None
        self._channel_name = None
        self._channel_number = None
        self._source = None
        self._source_list = []
        self._original_content_list = []
        self._content_mapping = {}
        self._duration = None
        self._content_uri = None
        self._id = None
        self._playing = False
        self._start_date_time = None
        self._program_media_type = None
        self._min_volume = None
        self._max_volume = None
        self._volume = None
        self._commands = []  # it is initialized by the update method
        self._cookies = None

        cookie = _bravia_auth(host, pin)
        if not cookie:
            self._state = STATE_OFF
            return
        else:
            self._cookies = cookie
            # update the state first of all
            self.update()

    def update(self):
        """Update TV info."""
        if self._cookies is None:
            cookie = _bravia_auth(self._host, self._pin)
            if not cookie:
                return
            else:
                self._cookies = cookie

        # Retrieve the latest data.
        try:
            resp = self._bravia_req_json("sony/avContent", _jdata_build("getPlayingContentInfo",
                                                                        None))
            if resp is None:
                self._state = STATE_OFF
            elif not resp.get('error'):
                self._state = STATE_ON
                playing_content_data = resp.get('result')[0]
                self._program_name = playing_content_data.get('programTitle')
                self._channel_name = playing_content_data.get('title')
                self._program_media_type = playing_content_data.get('programMediaType')
                self._channel_number = playing_content_data.get('dispNum')
                self._source = playing_content_data.get('source')
                self._content_uri = playing_content_data.get('uri')
                self._duration = playing_content_data.get('durationSec')
                self._start_date_time = playing_content_data.get('startDateTime')

                # update command data the very first time
                if len(self._commands) == 0:
                    resp = self._bravia_req_json("sony/system",
                                                 _jdata_build("getRemoteControllerInfo", None))
                    if not resp.get('error'):
                        self._commands = resp.get('result')[1]
                    else:
                        _LOGGER.error("JSON request error: " + json.dumps(resp, indent=4))

                resp = self._bravia_req_json("sony/audio",
                                             _jdata_build("getVolumeInformation", None))
                if not resp.get('error'):
                    results = resp.get('result')[0]
                    for result in results:
                        if result.get('target') == 'speaker':
                            self._volume = result.get('volume')
                            self._min_volume = result.get('minVolume')
                            self._max_volume = result.get('maxVolume')
                            self._muted = result.get('mute')
                else:
                    _LOGGER.error("JSON request error:" + json.dumps(resp, indent=4))

                if len(self._source_list) == 0:
                    self._load_source_list()
            else:
                self._state = STATE_OFF

        except Exception as exception_instance:  # pylint: disable=broad-except
            _LOGGER.error(exception_instance)
            self._state = STATE_OFF

    def _load_source_list(self):
        resp = self._bravia_req_json("sony/avContent",
                                     _jdata_build("getSourceList", {"scheme": "tv"}))
        if not resp.get('error'):
            self._original_content_list = []
            results = resp.get('result')[0]
            for result in results:
                if result['source'] == 'tv:dvbc':  # via cable
                    resp = self._bravia_req_json("sony/avContent",
                                                 _jdata_build("getContentList",
                                                              {"source": "tv:dvbc"}))
                    if not resp.get('error'):
                        self._original_content_list.extend(resp.get('result')[0])
                elif result['source'] == 'tv:dvbt':  # via DTT
                    resp = self._bravia_req_json("sony/avContent",
                                                 _jdata_build("getContentList",
                                                              {"source": "tv:dvbt"}))
                    if not resp.get('error'):
                        self._original_content_list.extend(resp.get('result')[0])

            source_list = []
            for content_item in self._original_content_list:
                title = content_item['title']
                source_list.append(title)
                self._content_mapping[title] = content_item['uri']
            self._source_list = source_list

    def _get_command_code(self, command_name):
        for command_data in self._commands:
            if command_data.get('name') == command_name:
                return command_data.get('value')
        return None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume / 100

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_BRAVIA

    @property
    def media_title(self):
        """Title of current playing media."""
        return_value = None
        if self._channel_name is not None:
            return_value = self._channel_name
            if self._program_name is not None:
                return_value = return_value + ': ' + self._program_name
        return return_value

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._channel_name

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._duration

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._bravia_req_json("sony/audio",
                              _jdata_build("setAudioVolume",
                                           {"target": "speaker", "volume": volume * 100}))

    def turn_on(self):
        """Turn the media player on."""
        _wakeonlan(self._mac)
        self._state = STATE_ON

    def turn_off(self):
        """Turn off media player."""
        self._send_req_ircc(self._get_command_code('PowerOff'))
        self._state = STATE_OFF

    def volume_up(self):
        """Volume up the media player."""
        self._send_req_ircc(self._get_command_code('VolumeUp'))

    def volume_down(self):
        """Volume down media player."""
        self._send_req_ircc(self._get_command_code('VolumeDown'))

    def mute_volume(self, mute):
        """Send mute command."""
        self._send_req_ircc(self._get_command_code('Mute'))

    def select_source(self, source):
        """Set the input source."""
        if source in self._content_mapping:
            uri = self._content_mapping[source]
            self._bravia_req_json("sony/avContent",
                                  _jdata_build("setPlayContent", {"uri": uri}))

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._playing = True
        self._send_req_ircc(self._get_command_code('Play'))

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self._send_req_ircc(self._get_command_code('Pause'))

    def media_next_track(self):
        """Send next track command."""
        self._send_req_ircc(self._get_command_code('Next'))

    def media_previous_track(self):
        """Send the previous track command."""
        self._send_req_ircc(self._get_command_code('Prev'))

    def _send_req_ircc(self, params):
        """Send an IRCC command via HTTP to Sony Bravia."""
        headers = {'SOAPACTION': 'urn:schemas-sony-com:service:IRCC:1#X_SendIRCC'}
        data = ("<?xml version=\"1.0\"?><s:Envelope xmlns:s=\"http://schemas.xmlsoap.org" +
                "/soap/envelope/\" " +
                "s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body>" +
                "<u:X_SendIRCC " +
                "xmlns:u=\"urn:schemas-sony-com:service:IRCC:1\"><IRCCCode>" +
                params+"</IRCCCode></u:X_SendIRCC></s:Body></s:Envelope>").encode("UTF-8")
        try:
            response = requests.post('http://' + self._host + '/sony/IRCC',
                                     headers=headers,
                                     cookies=self._cookies,
                                     data=data,
                                     timeout=TIMEOUT)
        except requests.exceptions.HTTPError as exception_instance:
            _LOGGER.error("[W] HTTPError: " + str(exception_instance))

        except Exception as exception_instance:  # pylint: disable=broad-except
            _LOGGER.error("[W] Exception: " + str(exception_instance))
        else:
            content = response.content
            return content

    def _bravia_req_json(self, url, params):
        try:
            response = requests.post('http://'+self._host+'/'+url,
                                     data=params.encode("UTF-8"),
                                     cookies=self._cookies,
                                     timeout=TIMEOUT)
        except requests.exceptions.HTTPError as exception_instance:
            _LOGGER.error("[W] HTTPError: " + str(exception_instance))

        except Exception as exception_instance:  # pylint: disable=broad-except
            _LOGGER.error("[W] Exception: " + str(exception_instance))

        else:
            html = json.loads(response.content.decode('utf-8'))
            return html
