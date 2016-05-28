"""
Support for interface with an Sony Bravia TV.

By Antonio Parraga Navarro

dedicated to Isabel

"""
import logging
import os
from homeassistant.loader import get_component
import urllib.request, base64
import json
import socket
import struct
import re
from subprocess import Popen, PIPE
from io import StringIO


from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON)

BRAVIA_CONFIG_FILE = 'bravia.conf'
CLIENTID = 'HomeAssistant'
NICKNAME = 'Home Assistant'
_TIMEOUT = 10

# Map ip to request id for configuring
_CONFIGURING = {}

_LOGGER = logging.getLogger(__name__)

SUPPORT_BRAVIA = SUPPORT_PAUSE | SUPPORT_VOLUME_STEP | \
                 SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | SUPPORT_PREVIOUS_TRACK | \
                 SUPPORT_NEXT_TRACK | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE


def config_from_file(filename, config=None):
    """Small configuration file management function."""
    if config:
        # We're writing configuration
        bravia_config = config_from_file(filename)
        if bravia_config is None:
            bravia_config = {}
        new_config = bravia_config.copy()
        new_config.update(config)
        try:
            with open(filename, 'w') as fdesc:
                io = StringIO()
                json.dump(new_config, io)
                fdesc.write(io.getvalue())
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

    host = config.get(CONF_HOST)

    if host is None:
        return #if no host configured, do not continue

    """Setup the Sony Bravia TV platform."""
    pin = None
    bravia_config = config_from_file(hass.config.path(BRAVIA_CONFIG_FILE))
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
        name = get_bravia_model(host)
        if name is None:
            _LOGGER.error("Sony bravia " + host + " is shutted down. Please turn on before configuring it...")
            name = "Sony Bravia TV"

    if pin is None:
        request_configuration(config, hass, add_devices_callback)
        return
    else:
        mac = get_mac_address(host)
        if not (mac is None):
            mac = mac.decode('utf8')
        # If we came here and configuring this host, mark as done
        if host in _CONFIGURING:
            request_id = _CONFIGURING.pop(host)
            configurator = get_component('configurator')
            configurator.request_done(request_id)
            _LOGGER.info('Discovery configuration done!')

        # Save config
        if not config_from_file(
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
        pin = data.get('pin')
        cookie = bravia_auth(host, "80", "sony/accessControl", pin)
        if not cookie:
            request_configuration(config, hass, add_devices_callback)
        else:
            setup_bravia(config, pin, hass, add_devices_callback)

    _CONFIGURING[host] = configurator.request_config(
        hass, name, bravia_configuration_callback,
        description=('Enter the Pin shown on your Sony Bravia TV'),
        description_image="/static/images/smart-tv.png",
        submit_caption="Confirm",
        fields=[{'id': 'pin', 'name': 'Enter the pin', 'type': ''}]
    )

def DISCOVER_via_SSDP (service = "urn:schemas-sony-com:service:ScalarWebAPI:1", retries = 10):
    if retries <= 0:
        return None
    import select, re
    SSDP_ADDR = "239.255.255.250";
    SSDP_PORT = 1900;
    SSDP_MX = 1;
    SSDP_ST = service;

    ssdpRequest = "M-SEARCH * HTTP/1.1\r\n" + \
                  "HOST: %s:%d\r\n" % (SSDP_ADDR, SSDP_PORT) + \
                  "MAN: \"ssdp:discover\"\r\n" + \
                  "MX: %d\r\n" % (SSDP_MX, ) + \
                  "ST: %s\r\n" % (SSDP_ST, ) + "\r\n";

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5.0)
    dest = socket.gethostbyname(SSDP_ADDR)
    sock.sendto(ssdpRequest.encode('UTF-8'), (dest, SSDP_PORT))
    sock.settimeout(5.0)
    while True:
        try:
            data = sock.recv(1024)
            response = data.decode('utf-8')
            if(re.search("BRAVIA", response)):
                match = re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", response)
                if match:
                    return match.group()
                else:
                    return None
        except socket.timeout:
            break

    return DISCOVER_via_SSDP(service, retries - 1)

def wakeonlan(ethernet_address):
    addr_byte = ethernet_address.split(':')
    hw_addr = struct.pack('BBBBBB', int(addr_byte[0], 16),
                          int(addr_byte[1], 16),
                          int(addr_byte[2], 16),
                          int(addr_byte[3], 16),
                          int(addr_byte[4], 16),
                          int(addr_byte[5], 16))
    msg = b'\xff' * 6 + hw_addr * 16
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.sendto(msg, ('<broadcast>', 9))
    s.close()

def bravia_auth ( ip, port, url, pin ):

    authorization = json.dumps(
        {	"method":"actRegister",
             "params":[
                 {
                     "clientid": CLIENTID,
                     "nickname": NICKNAME,
                     "level":"private"},[
                     {
                         "value":"yes",
                         "function":"WOL"}
                 ]
             ],
             "id":1,
             "version":"1.0"}
    ).encode('utf-8')

    req = urllib.request.Request('http://'+ip+':'+port+'/'+url, authorization)
    cookie = None
    response = None

    if pin:
        username = ''
        base64string = base64.encodebytes(('%s:%s' % (username, pin)).encode()).decode().replace('\n', '')
        req.add_header("Authorization", "Basic %s" % base64string)
        req.add_header("Connection", "keep-alive")

    try:
        response = urllib.request.urlopen(req, None, _TIMEOUT)

    except urllib.request.HTTPError as e:
        print ("[W] HTTPError: " + str(e.code))
        return None

    except urllib.request.URLError as e:
        print ("[W] URLError: " + str(e.reason))
        return None

    else:
        for h in response.headers:
            if h.find("Set-Cookie") > -1:
                cookie=h
        if cookie:
            cookie = response.headers['Set-Cookie']
            return cookie
        return None

def get_bravia_model( ip ):
    try:
        req = urllib.request.Request('http://'+ip+':52323/dmr.xml')
        response = urllib.request.urlopen(req, None, _TIMEOUT)

    except urllib.request.HTTPError as e:
        print ("[W] HTTPError: " + str(e.code))

    except urllib.request.URLError as e:
        print ("[W] URLError: " + str(e.reason))

    else:
        data = response.read()

        return data

def get_mac_address( ip ):
    pid = Popen(["arp", "-n", ip], stdout=PIPE)
    s = pid.communicate()[0]
    mac = re.search(r"(([a-f\d]{1,2}\:){5}[a-f\d]{1,2})".encode('UTF-8'), s).groups()[0]
    return mac

# pylint: disable=abstract-method
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
        self._start_date_time = None
        self._program_media_type = None
        self._min_volume = None
        self._max_volume = None
        self._volume = None
        self._commands = [] #it is initialized by the update method
        self._cookie = None

        cookie = bravia_auth(host, "80", "sony/accessControl", pin)
        if not cookie:
            self._state = STATE_OFF
            return
        else:
            self._cookie = cookie
            #update the state first of all
            self.update()

    def update(self):

        if self._cookie is None:
            cookie = bravia_auth(self._host, "80", "sony/accessControl", self._pin)
            if not cookie:
                return
            else:
                self._cookie = cookie

        """Retrieve the latest data."""
        try:
            resp = self.bravia_req_json("sony/avContent", self.jdata_build("getPlayingContentInfo", None));
            if resp is None:
                self._state = STATE_OFF
            elif not resp.get('error'):
                """
                for example:
                {
    "result": [
        {
            "programMediaType": "tv",
            "uri": "tv:dvbt?trip=8916.1016.570&srvName=La 1",
            "startDateTime": "2016-05-22T23:31:56+0200",
            "title": "La 1",
            "tripletStr": "8916.1016.570",
            "dispNum": "001",
            "programTitle": "Los Angeles De Charlie: Al Limite",
            "source": "tv:dvbt",
            "durationSec": 5638
        }
    ],
    "id": 1
}
                """
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

                #update command data the very first time
                if len(self._commands) == 0:
                    resp = self.bravia_req_json("sony/system", self.jdata_build("getRemoteControllerInfo", None))
                    if not resp.get('error'):
                        self._commands = resp.get('result')[1]
                    else:
                        print ("JSON request error", json.dumps(resp, indent=4))

                resp = self.bravia_req_json("sony/audio", self.jdata_build("getVolumeInformation", None))
                if not resp.get('error'):
                    results = resp.get('result')[0]
                    for result in results:
                        if result.get('target') == 'speaker':
                            self._volume = result.get('volume')
                            self._min_volume = result.get('minVolume')
                            self._max_volume = result.get('maxVolume')
                            self._muted = result.get('mute')
                else:
                    print ("JSON request error", json.dumps(resp, indent=4))

                resp = self.bravia_req_json("sony/avContent", self.jdata_build("getSourceList", {"scheme":"tv"}))
                if not resp.get('error'):
                    self._original_content_list = []
                    results = resp.get('result')[0]
                    for result in results:
                        """
                        [
{
"programMediaType": "tv",
"tripletStr": "8916.1016.570",
"title": "La 1",
"dispNum": "001",
"index": 0,
"uri": "tv:dvbt?trip=8916.1016.570&srvName=La 1"
},
{
"programMediaType": "tv",
"tripletStr": "8916.1016.571",
"title": "La 2",
"dispNum": "002",
"index": 1,
"uri": "tv:dvbt?trip=8916.1016.571&srvName=La 2"
},
..."""

                        if result['source'] == 'tv:dvbc': #via cable
                            resp = self.bravia_req_json("sony/avContent", self.jdata_build("getContentList", {"source": "tv:dvbc"}))
                            if not resp.get('error'):
                                self._original_content_list.extend(resp.get('result')[0])
                        elif result['source'] == 'tv:dvbt': #via DTT
                            resp = self.bravia_req_json("sony/avContent", self.jdata_build("getContentList", {"source": "tv:dvbt"}))
                            if not resp.get('error'):
                                self._original_content_list.extend(resp.get('result')[0])

                    source_list = []
                    for content_item in self._original_content_list:
                        title = content_item['title']
                        source_list.append( title )
                        self._content_mapping[title] = content_item['uri']
                    self._source_list = source_list


#                resp = self.bravia_req_json("sony/avContent", self.jdata_build("getContentList", {"source":"tv:dvbt"}))
#                if not resp.get('error'):
#                    print (json.dumps(resp, indent=4))
#                else:
#                    print ("JSON request error", json.dumps(resp, indent=4))

            else:
                self._state = STATE_OFF

        except Exception as e:
            print(e)
            self._state = STATE_OFF

    def getCommandCode(self, command_name):
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
        if not(self._channel_name is None):
            return_value = self._channel_name
            if not(self._program_name is None):
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
        self.bravia_req_json("sony/audio", self.jdata_build("setAudioVolume", {"target": "speaker", "volume" : volume * 100}))

    def turn_on(self):
        """Turn the media player on."""
        wakeonlan(self._mac)
        self._state = STATE_OFF

    def turn_off(self):
        """Turn off media player."""
        self.send_req_ircc(self.getCommandCode('PowerOff'))
        self._state = STATE_OFF

    def volume_up(self):
        """Volume up the media player."""
        self.send_req_ircc(self.getCommandCode('VolumeUp'))

    def volume_down(self):
        """Volume down media player."""
        self.send_req_ircc(self.getCommandCode('VolumeDown'))

    def mute_volume(self, mute):
        """Send mute command."""
        self.send_req_ircc(self.getCommandCode('Mute'))

    def select_source(self, source):
        """Set the input source."""
        if source in self._content_mapping:
            uri = self._content_mapping[source]
            resp = self.bravia_req_json("sony/avContent", self.jdata_build("setPlayContent", {"uri": uri}))
            if not resp.get('error'):
                print (json.dumps(resp, indent=4))
            else:
                print ("JSON request error", json.dumps(resp, indent=4))

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._playing = True
        self.send_req_ircc(self.getCommandCode('Play'))

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self.send_req_ircc(self.getCommandCode('Pause'))

    def media_next_track(self):
        """Send next track command."""
        self.send_req_ircc(self.getCommandCode('Next'))

    def media_previous_track(self):
        """Send the previous track command."""
        self.send_req_ircc(self.getCommandCode('Prev'))


    def send_req_ircc( self, params ):
        """ Send an IRCC command via HTTP to Sony Bravia """
        req = urllib.request.Request('http://' + self._host + ':80/sony/IRCC', ("<?xml version=\"1.0\"?><s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body><u:X_SendIRCC xmlns:u=\"urn:schemas-sony-com:service:IRCC:1\"><IRCCCode>"+params+"</IRCCCode></u:X_SendIRCC></s:Body></s:Envelope>").encode("UTF-8"))
        req.add_header('SOAPACTION', 'urn:schemas-sony-com:service:IRCC:1#X_SendIRCC')
        req.add_header('Cookie', self._cookie)

        try:
            response = urllib.request.urlopen(req, None, _TIMEOUT)
        except urllib.request.HTTPError as e:
            print ("[W] HTTPError: " + str(e.code))

        except urllib.request.URLError as e:
            print ("[W] URLError: " + str(e.reason))
        else:
            tree = response.read()
            return tree

    def bravia_req_json( self, url, params ):
        req = urllib.request.Request('http://'+ self._host +':80/'+url, params.encode("UTF-8"))
        req.add_header('Cookie', self._cookie)
        try:
            response = urllib.request.urlopen(req, None, _TIMEOUT)

        except urllib.request.HTTPError as e:
            print ("[W] HTTPError: " + str(e.code))

        except urllib.request.URLError as e:
            print ("[W] URLError: " + str(e.reason))

        else:
            html = json.loads(response.readall().decode('utf-8'))
            return html

    def jdata_build(self, method, params):
        if params:
            ret =  json.dumps({"method":method,"params":[params],"id":1,"version":"1.0"})
        else:
            ret =  json.dumps({"method":method,"params":[],"id":1,"version":"1.0"})
        return ret