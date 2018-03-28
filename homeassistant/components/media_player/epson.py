"""
Support for Epson projector.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/media_player.epson/
"""
import asyncio
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.media_player import (
    DOMAIN, MEDIA_PLAYER_SCHEMA, PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE, SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP,
    MediaPlayerDevice)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_PORT, CONF_SSL,
    CONTENT_TYPE_JSON, HTTP_OK, STATE_OFF, STATE_ON)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv

KEY_COMMANDS = {
    "TURN_ON": [('KEY', '3B')],
    "TURN_OFF": [('KEY', '3B'), ('KEY', '3B')],
    "HDMILINK": [('jsoncallback', 'HDMILINK?')],
    "PWR": [('jsoncallback', 'PWR?')],
    "SOURCE": [('jsoncallback', 'SOURCE?')],
    "CMODE": [('jsoncallback', 'CMODE?')],
    "VOLUME": [('jsoncallback', 'VOL?')],
    "CMODE_AUTO": [('CMODE', '00')],
    "CMODE_CINEMA": [('CMODE', '15')],
    "CMODE_NATURAL": [('CMODE', '07')],
    "CMODE_BRIGHT": [('CMODE', '0C')],
    "CMODE_DYNAMIC": [('CMODE', '06')],
    "CMODE_3DDYNAMIC": [('CMODE', '18')],
    "CMODE_3DCINEMA": [('CMODE', '17')],
    "CMODE_3DTHX": [('CMODE', '19')],
    "CMODE_BWCINEMA": [('CMODE', '20')],
    "CMODE_ARGB": [('CMODE', '21')],
    "CMODE_DCINEMA": [('CMODE', '22')],
    "CMODE_THX": [('CMODE', '13')],
    "CMODE_GAME": [('CMODE', '0D')],
    "CMODE_STAGE": [('CMODE', '16')],
    "CMODE_AUTOCOLOR": [('CMODE', 'C1')],
    "CMODE_XV": [('CMODE', '0B')],
    "CMODE_THEATRE": [('CMODE', '05')],
    "CMODE_THEATREBLACK": [('CMODE', '09')],
    "CMODE_THEATREBLACK2": [('CMODE', '0A')],
    "VOL_UP": [('KEY', '56')],
    "VOL_DOWN": [('KEY', '57')],
    "MUTE": [('KEY', 'D8')],
    "HDMI1": [('KEY', '4D')],
    "HDMI2": [('KEY', '40')],
    "PC": [('KEY', '44')],
    "VIDEO": [('KEY', '46')],
    "USB": [('KEY', '85')],
    "LAN": [('KEY', '53')],
    "WFD": [('KEY', '56')],
    "PLAY": [('KEY', 'D1')],
    "PAUSE": [('KEY', 'D3')],
    "STOP": [('KEY', 'D2')],
    "BACK": [('KEY', 'D4')],
    "FAST": [('KEY', 'D5')],
}

TIMEOUT_TIMES = {
    'TURN_ON': 40,
    'TURN_OFF': 10,
    'SOURCE': 5,
    'ALL': 3
}

DEFAULT_SOURCES = {
    'HDMI1': 'HDMI1',
    'HDMI2': 'HDMI2',
    'PC': 'PC',
    'VIDEO': 'VIDEO',
    'USB': 'USB',
    'LAN': 'LAN',
    'WFD': 'WiFi Direct'
}

SOURCE_LIST = {
    '30': 'HDMI1',
    '10': 'PC',
    '40': 'VIDEO',
    '52': 'USB',
    '53': 'LAN',
    '56': 'WDF',
    'A0': 'HDMI2'
}

INV_SOURCES = {v: k for k, v in DEFAULT_SOURCES.items()}

CMODE_LIST = {
    '00': 'Auto',
    '15': 'Cinema',
    '07': 'Natural',
    '0C': 'Bright Cinema/Living',
    '06': 'Dynamic',
    '17': '3D Cinema',
    '18': '3D Dynamic',
    '19': '3D THX',
    '20': 'B&W Cinema',
    '21': 'Adobe RGB',
    '22': 'Digital Cinema',
    '13': 'THX',
    '0D': 'Game',
    '16': 'Stage',
    'C1': 'AutoColor',
    '0B': 'x.v. color',
    '05': 'Theatre',
    '09': 'Theatre Black 1/HD',
    '0A': 'Theatre Black 2/Silver Screen'
}

CMODE_LIST_SET = {
    'cinema': 'CMODE_CINEMA',
    'natural': 'CMODE_NATURAL',
    'bright cinema': 'CMODE_BRIGHT',
    'dynamic': 'CMODE_DYNAMIC',
    '3ddynamic': 'CMODE_3DDYNAMIC',
    '3dcinema': 'CMODE_3DCINEMA',
    'auto': 'CMODE_AUTO',
    '3dthx': 'CMODE_3DTHX',
    'bwcinema': 'CMODE_BWCINEMA',
    'adobe rgb': 'CMODE_ARGB',
    'digital cinema': 'CMODE_DCINEMA',
    'thx': 'CMODE_THX',
    'game': 'CMODE_GAME',
    'stage': 'CMODE_STAGE',
    'autocolor': 'CMODE_AUTOCOLOR',
    'xv': 'CMODE_XV',
    'theatre': 'CMODE_THEATRE',
    'theatre black': 'CMODE_THEATREBLACK',
    'theatre black 2': 'CMODE_THEATREBLACK2'
}

DATA_EPSON = 'epson'
DEFAULT_NAME = 'EPSON Projector'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=80): cv.port,
    vol.Optional(CONF_SSL, default=False): cv.boolean
})
ATTR_CMODE = 'cmode'
SUPPORT_CMODE = 33001
ACCEPT_ENCODING = "gzip, deflate"
ACCEPT_HEADER = CONTENT_TYPE_JSON
EPSON_ERROR_CODE = 'ERR'
EPSON_CODES = {
    'ON': '01'
}
TIMEOUT = 15
SUPPORT_EPSON = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE |\
            SUPPORT_CMODE | SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_STEP | \
            SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK

EPSON_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Optional(ATTR_CMODE): cv.string
})

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Epson media player platform."""
    if DATA_EPSON not in hass.data:
        hass.data[DATA_EPSON] = []
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    try:
        epson = EpsonProjector(
            hass, name, host,
            config.get(CONF_PORT), config.get(CONF_SSL), KEY_COMMANDS)
        epson.update()
    except (aiohttp.client_exceptions.ClientConnectorError,
            asyncio.TimeoutError):
        raise PlatformNotReady
    if epson:
        hass.data[DATA_EPSON].append(epson)
        async_add_devices([epson], update_before_add=True)

    @asyncio.coroutine
    def async_service_handler(service):
        """Handle for services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            devices = [device for device in hass.data[DATA_EPSON]
                       if device.entity_id in entity_ids]
        else:
            devices = hass.data[DATA_EPSON]
        for device in devices:
            if service.service == ATTR_CMODE:
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
        """Initialize entity to control Epson projector."""
        self._hass = hass
        self._name = name
        self._host = host
        self._port = port
        self._cmode = None
        self._source_list = list(DEFAULT_SOURCES.values())
        self._source = None
        self._volume = None
        self.key_commands = key_commands
        self._encryption = encryption
        self._state = None
        http_protocol = 'https' if self._encryption else 'http'
        self._http_url = '{http_protocol}://{host}:{port}/cgi-bin/'.format(
            http_protocol=http_protocol,
            host=self._host,
            port=self._port)
        referer = "{http_protocol}://{host}:{port}/cgi-bin/webconf".format(
            http_protocol=http_protocol,
            host=self._host,
            port=self._port)
        self._headers = {
            "Accept-Encoding": ACCEPT_ENCODING,
            "Accept": CONTENT_TYPE_JSON,
            "Referer": referer
        }
        self.websession = async_create_clientsession(
            hass,
            verify_ssl=False)

    @asyncio.coroutine
    def update(self):
        """Update state of device."""
        is_turned_on = yield from self.get_property('PWR')
        if is_turned_on and is_turned_on == EPSON_CODES['ON']:
            self._state = STATE_ON
            cmode = yield from self.get_property('CMODE')
            if cmode and cmode in CMODE_LIST:
                self._cmode = CMODE_LIST[cmode]
            source = yield from self.get_property('SOURCE')
            if source and souce in SOURCE_LIST:
                self._source = SOURCE_LIST[source]
            volume = yield from self.get_property('VOLUME')
            if volume:
                self._volume = volume
        else:
            self._state = STATE_OFF

    @asyncio.coroutine
    def get_property(self, command):
        """Get property state from device."""
        try:
            if command in TIMEOUT_TIMES:
                timeout = TIMEOUT_TIMES[command]
            else:
                timeout = TIMEOUT_TIMES['ALL']
            with async_timeout.timeout(timeout):
                response = yield from self.websession.get(
                    url='{url}{type}'.format(
                        url=self._http_url,
                        type='json_query'),
                    params=KEY_COMMANDS[command],
                    headers=self._headers)
                if response.status != HTTP_OK:
                    _LOGGER.warning(
                        "Error message %d from Epson.", response.status)
                    return False
                resp = yield from response.json()
                reply_code = resp['projector']['feature']['reply']
                return reply_code
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error getting info")
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
        """Turn on epson."""
        return self.send_command('TURN_ON')

    @asyncio.coroutine
    def async_turn_off(self):
        """Turn off epson."""
        return self.send_command('TURN_OFF')

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def source(self):
        """Get current input sources."""
        return self._source

    @property
    def cmode(self):
        """Get CMODE/color mode from Epson."""
        return self._cmode

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return self._volume

    @asyncio.coroutine
    def select_cmode(self, cmode):
        """Set color mode in Epson."""
        if cmode in CMODE_LIST_SET:
            return self.send_command(CMODE_LIST_SET[cmode])

    @asyncio.coroutine
    def async_select_source(self, source):
        """Select input source."""
        _LOGGER.debug("select source")
        selected_source = INV_SOURCES[source]
        return self.send_command(selected_source)

    @asyncio.coroutine
    def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) sound."""
        return self.send_command("MUTE")

    @asyncio.coroutine
    def async_volume_up(self):
        """Increase volume."""
        _LOGGER.debug("volume up")
        return self.send_command("VOL_UP")

    @asyncio.coroutine
    def async_volume_down(self):
        """Decrease volume."""
        return self.send_command("VOL_DOWN")

    @asyncio.coroutine
    def async_media_play(self):
        """Play media via Epson."""
        return self.send_command("PLAY")

    @asyncio.coroutine
    def async_media_pause(self):
        """Pause media via Epson."""
        return self.send_command("PAUSE")

    @asyncio.coroutine
    def async_media_next_track(self):
        """Skip to next."""
        return self.send_command("FAST")

    @asyncio.coroutine
    def async_media_previous_track(self):
        """Skip to previous."""
        return self.send_command("BACK")

    @asyncio.coroutine
    def send_command(self, command):
        """Send command to Epson."""
        _LOGGER.debug("COMMAND %s", command)
        params = self.key_commands[command]
        try:
            if command in TIMEOUT_TIMES:
                timeout = TIMEOUT_TIMES[command]
            else:
                timeout = TIMEOUT_TIMES['ALL']
            with async_timeout.timeout(timeout):
                url = '{url}{type}'.format(
                    url=self._http_url,
                    type='directsend')
                response = yield from self.websession.get(
                    url,
                    params=params,
                    headers=self._headers)
            if response.status != HTTP_OK:
                return None
            return True
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error sending command")
        return None

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attributes = {}
        if self._cmode is not None:
            attributes[ATTR_CMODE] = self._cmode
        return attributes
