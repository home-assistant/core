"""
Support for Epson projector

For more details about this component, please refer to the documentation at
https://home-assistant.io/cookbook/python_component_basic_state/
"""
import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import async_timeout
import asyncio
import aiohttp

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, MediaPlayerDevice, SUPPORT_TURN_ON, SUPPORT_TURN_OFF,SUPPORT_SELECT_SOURCE, MEDIA_PLAYER_SCHEMA, DOMAIN,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP, SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK
)

""" ,SUPPORT_PLAY, SUPPORT_PAUSE, SUPPORT_STOP"""

from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.const import (ATTR_ENTITY_ID, CONF_HOST,CONF_NAME,CONF_PORT,CONF_SSL, STATE_ON, STATE_OFF, STATE_UNKNOWN, STATE_PLAYING)

import homeassistant.util as util

DEPENDENCIES = []

KEY_COMMANDS = {
    "TURN_ON" : [('KEY', '3B')],
    "TURN_OFF": [('KEY', '3B'), ('KEY', '3B')],
    "HDMILINK" : [('jsoncallback', 'HDMILINK?')],
    "CMODE" : [('jsoncallback', 'CMODE?')],
    "CMODE_CINEMA" : [('CMODE', '15')],
    "CMODE_NATURAL" : [('CMODE', '07')],
    "CMODE_BRIGHT" : [('CMODE', '0C')],
    "CMODE_DYNAMIC" : [('CMODE', '06S')],
    "VOL_UP" : [('KEY', '56')],
    "VOL_DOWN" : [('KEY', '57')],
    "MUTE" : [('KEY', '3E')],
    "HDMI1" : [('KEY', '4D')],
    "HDMI2" : [('KEY', '40')],
    "PC" : [('KEY', '44')],
    "VIDEO" : [('KEY', '46')],
    "USB" : [('KEY', '85')],
    "LAN" : [('KEY', '53')],
    "WFD" : [('KEY', '56')],
    "PLAY" : [('KEY', 'D1')],
    "PAUSE" : [('KEY', 'D3')],
    "STOP" : [('KEY', 'D2')],
    "BACK" : [('KEY', 'D4')],
    "FAST" : [('KEY', 'D5')],
}

DEFAULT_SOURCES = {
    'HDMI1' : 'HDMI1',
    'HDMI2' : 'HDMI2',
    'PC'    : 'PC',
    'VIDEO'    : 'VIDEO',
    'USB'    : 'USB',
    'LAN'    : 'LAN',
    'WFD'   : 'WiFi Direct'
}

INV_SOURCES = {v: k for k, v in DEFAULT_SOURCES.items()}

CMODE_LIST = {
    '15' : 'Cinema',
    '07' : 'Natural',
    '0C' : 'Bright Cinema',
    '06' : 'Dynamic'
}

CMODE_LIST_SET = {
    'cinema': 'CMODE_CINEMA',
    'natural' : 'CMODE_NATURAL',
    'bright cinema' : 'CMODE_BRIGHT',
    'dynamic' : 'CMODE_DYNAMIC'
}

DATA_EPSON = 'epson'
DEFAULT_NAME = 'EPSON Projector'

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST) : cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME) : cv.string,
    vol.Optional(CONF_PORT, default=80) : cv.port,
    vol.Optional(CONF_SSL, default=False) : cv.boolean
})
ATTR_CMODE = 'cmode'
SUPPORT_CMODE = 33001

SUPPORT_EPSON = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE | SUPPORT_CMODE | \
                SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_STEP | \
                 SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK
                 # SUPPORT_PLAY | SUPPORT_PAUSE | SUPPORT_STOP


EPSON_SCHEMA =  MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Optional(ATTR_CMODE): cv.string
})

# ATTR_TO_PROPERTY = ATTR_TO_PROPERTY.extend(ATTR_CMODE)

_LOGGER = logging.getLogger(__name__)

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):

    if DATA_EPSON not in hass.data:
        hass.data[DATA_EPSON] = []

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    epson = EpsonProjector(hass, name, host, config.get(CONF_PORT), config.get(CONF_SSL), KEY_COMMANDS)

    epson.update()
    hass.data[DATA_EPSON].append(epson)
    async_add_devices([epson], update_before_add=True)
    # async_add_devices([epson])

    @asyncio.coroutine
    def async_service_handler(service):
        """Handle for services."""
        entity_ids = service.data.get('entity_id')
        if entity_ids:
            devices = [device for device in hass.data[DATA_EPSON]
                       if device.entity_id in entity_ids]
        else:
            devices = hass.data[DATA_EPSON]
        for device in devices:
            if (service.service == ATTR_CMODE):
                cmode = service.data.get(ATTR_CMODE).lower()
                if cmode in CMODE_LIST_SET:
                    yield from device.select_cmode(cmode)
            yield from device.update()
    hass.services.async_register(
        DOMAIN, ATTR_CMODE, async_service_handler,
        schema=EPSON_SCHEMA)
    return True

class EpsonProjector(MediaPlayerDevice):
    """Representation of Epson Projector Device."""

    def __init__(self, hass, name, host, port, encryption, key_commands):
        self._hass = hass
        self._name = name
        self._host = host
        self._port = port
        self._cmode = None
        self._source_list = list(DEFAULT_SOURCES.values())
        self.KEY_COMMANDS = key_commands
        self._encryption = encryption
        self._state = STATE_UNKNOWN
        http_protocol = 'https' if self._encryption else 'http'
        self._http_url = '{http_protocol}://{host}:{port}/cgi-bin/'.format(http_protocol=http_protocol, host=self._host, port=self._port)
        self._headers = {
            "Accept-Encoding" : "gzip, deflate",
            "Accept" : "application/json, text/javascript",
            "Referer": "{http_protocol}://{host}:{port}/cgi-bin/webconf".format(http_protocol=http_protocol,host=self._host,port=self._port)
        };

        self.websession = async_create_clientsession(hass, verify_ssl=self._encryption)
        self.websession_action = async_create_clientsession(hass, verify_ssl=self._encryption)
        self.update()

    @asyncio.coroutine
    def update(self):
        """Update state of device."""
        # self._state = STATE_ON
        # self._cmode = CMODE_LIST['15']
        # return True
        try:
            with async_timeout.timeout(10, loop=self._hass.loop):
                response = yield from self.websession.get(
                    url='{url}{type}'.format(url=self._http_url, type='json_query' ),
                    params=KEY_COMMANDS['CMODE'],
                    headers=self._headers)
            if response.status != 200:
                    _LOGGER.warning("[%s] Error %d on Epson.", DOMAIN, response.status)
                    self._state = STATE_OFF
            response_json = yield from response.json()
            if (response_json['projector']['feature']['reply'] == 'ERR'):
                self._state = STATE_OFF
                # self._cmode = CMODE_LIST['15']
            else:
                self._state = STATE_ON
                self._cmode = CMODE_LIST[response_json['projector']['feature']['reply']]
                # if self._cmode is not None:
                #     self._state = STATE_PLAYING
        except (aiohttp.ClientError):
            _LOGGER.error("[%s] Error getting info", DOMAIN)
            self._state = STATE_OFF
            return False
        return True



    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_EPSON

    @asyncio.coroutine
    def async_turn_on(self):
        """Turn on epson"""
        return self.sendCommand('TURN_ON')

    @asyncio.coroutine
    def async_turn_off(self):
        """Turn off epson"""
        return self.sendCommand('TURN_OFF')

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def cmode(self):
        return self._cmode

    @asyncio.coroutine
    def select_cmode(self, cmode):
        if cmode in CMODE_LIST_SET:
            return self.sendCommand(CMODE_LIST_SET[cmode])

    @asyncio.coroutine
    def async_select_source(self, source):
        """Select input source."""
        _LOGGER.info("select source")
        selected_source = INV_SOURCES[source]
        return self.sendCommand(selected_source)

    @asyncio.coroutine
    def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) projector. It also mutes video input!  """
        return self.sendCommand("MUTE")

    @asyncio.coroutine
    def async_volume_up(self):
        """Increase volume."""
        _LOGGER.info("volume up")
        return self.sendCommand("VOL_UP")

    @asyncio.coroutine
    def async_volume_down(self):
        """Decrease volume."""
        return self.sendCommand("VOL_DOWN")

    @asyncio.coroutine
    def async_media_play(self):
        """Play."""
        return self.sendCommand("PLAY")

    @asyncio.coroutine
    def async_media_pause(self):
        """Play."""
        return self.sendCommand("PAUSE")

    @asyncio.coroutine
    def async_media_next_track(self):
        """Skip to next."""
        return self.sendCommand("FAST")

    @asyncio.coroutine
    def async_media_previous_track(self):
        """Skip to previous."""
        return self.sendCommand("BACK")

    @asyncio.coroutine
    def sendCommand(self, command):
        _LOGGER.info("COMMAND %s", command)
        params = self.KEY_COMMANDS[command]
        try:
            url = '{url}{type}'.format(url=self._http_url, type='directsend')
            # with async_timeout.timeout(10, loop=self._hass.loop):
            response = yield from self.websession_action.get(url,params=params,headers=self._headers)
            if response.status != 200:
                return None
            return True
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("[%s] Error getting info", DOMAIN)
        return None

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attributes = {}

        if self._cmode is not None:
            attributes[ATTR_CMODE] = self._cmode

        return attributes


#curl 'http://192.168.4.131/cgi-bin/json_query?jsoncallback=HDMILINK?%2001&_=1520179300356' -H 'Accept-Encoding: gzip, deflate'  -H 'Accept: application/json, text/javascript, */*; q=0.01' -H 'Referer: http://192.168.4.131/cgi-bin/webconf' -H 'X-Requested-With: XMLHttpRequest' -H 'Connection: keep-alive' --compressed
# def setup(hass, config):
#     """Setup the Hello State component. """
#     _LOGGER.info("The 'hello state' component is ready!")
#     text = config[DOMAIN].get(CONF_TEXT, DEFAULT_TEXT)
#     hass.states.set('first.Hello_State', text)
#
#     return True
