"""
Ryobi platform for the cover component.
For more details about this platform, please refer to the documentation
https://home-assistant.io/components/ryobiGDO/
"""
import logging
import json
import socket
import requests
import voluptuous as vol
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
from homeassistant.components.cover import (CoverDevice, PLATFORM_SCHEMA, SUPPORT_OPEN, SUPPORT_CLOSE)
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.const import (
    CONF_DEVICE, CONF_USERNAME, CONF_PASSWORD,
    STATE_UNKNOWN, STATE_CLOSED, STATE_OPEN, CONF_COVERS)

REQUIREMENTS = ['websocket-client==0.37.0']

_LOGGER = logging.getLogger(__name__)

COVER_SCHEMA = vol.Schema({
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COVERS): vol.Schema({cv.slug: COVER_SCHEMA}),
})

SCAN_INTERVAL = timedelta(seconds=30)

RYOBI_APIKEY_URL="https://tti.tiwiconnect.com/api/login"
RYOBI_DEVICES_URL="https://tti.tiwiconnect.com/api/devices"
RYOBI_WS_URL = "wss://tti.tiwiconnect.com/api/wsrpc"

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Ryobi covers."""

    covers = []
    devices = config.get(CONF_COVERS)

    for device_id, device_config in devices.items():
        apiKey = retrieve_apiKey(device_config.get(CONF_USERNAME),\
                 device_config.get(CONF_PASSWORD),\
                device_config.get(CONF_DEVICE, device_id))
        device_id_valid = check_device_id(device_config.get(CONF_USERNAME),\
                          device_config.get(CONF_PASSWORD),\
                          device_config.get(CONF_DEVICE, device_id))
        if apiKey != None and device_id_valid:
            args = {
                'name': "ryobigdo_" + device_config.get(CONF_DEVICE, device_id),
                'device_id': device_config.get(CONF_DEVICE, device_id),
                'username': device_config.get(CONF_USERNAME),
                'password': device_config.get(CONF_PASSWORD),
                'apiKey': apiKey
            }
            covers.append(RyobiCover(hass, args, \
                          supported_features=(SUPPORT_OPEN | SUPPORT_CLOSE)))

    add_devices(covers)

def retrieve_apiKey(username, password, device_id):
    """Getting apiKey from Ryobi."""
    _LOGGER.debug("Getting apiKey from Ryobi")
    resp = requests.post(RYOBI_APIKEY_URL, params={
        'username': username,
        'password': password
    })
    _LOGGER.debug(resp.status_code)
    if resp.status_code == 200:
        _LOGGER.debug("auth OK. apiKey retrieved")
        return resp.json()['result']['metaData']['wskAuthAttempts'][0]['apiKey']
    else:
        _LOGGER.error("auth KO. No apiKey retrieved. cover "\
         + device_id +" will not be add")
        return None

def check_device_id (username, password, device_id):
    """Checking device_id from Ryobi."""
    device_found = False
    _LOGGER.debug("Checking device_id from Ryobi")
    resp = requests.get(RYOBI_DEVICES_URL, params={
        'username': username,
        'password': password
    })
    if resp.status_code == 200:
        if len(resp.json()['result']) == 0:
            _LOGGER.error("no device paired in your RyobiGDO account")
        else:
            _LOGGER.debug("device(s) paired in your RyobiGDO account")
            for data in resp.json()['result']:
                if data['varName'] == device_id:
                    device_found = True
    else:
        _LOGGER.error("Failed to retrieve devices information")
    if device_found == True:
        _LOGGER.info("Adding device " + device_id +" to RyobiGDO Covers")
        return True
    else:
        _LOGGER.error("Device_id " + device_id +\
        " is not among your devices. It will not be add")
        return False

class RyobiCover(CoverDevice):
    """Representation of a ryobi cover."""

    # pylint: disable=no-self-use
    def __init__(self, hass, args, supported_features=None):
        """Initialize the cover."""
        self.hass = hass
        self._name = args['name']
        self._device_id = args['device_id']
        self._username = args['username']
        self._password = args['password']
        self._api_key = args['apiKey']
        self._supported_features = supported_features
        self._door_state = STATE_UNKNOWN
        self.time_in_state = None
        self._unsub_listener_cover = None
        self._available = True
        from websocket import create_connection
        self._connection = create_connection
        self._ws = None

    def get_ws(self):
        """Check if the websocket is setup and connected."""
        _LOGGER.debug("Getting websocket")

        if self._ws is None:
            try:
                self._ws = self._connection((RYOBI_WS_URL),timeout=1)
                authMssg=json.dumps({'jsonrpc':'2.0','id':3,'method':\
                'srvWebSocketAuth','params': {'varName':self._username,\
                'apiKey':self._api_key}})
                _LOGGER.debug(authMssg)
                self._ws.send(authMssg)
                result = self._ws.recv()
                _LOGGER.debug("Answer")
                _LOGGER.debug(result)
            except (socket.timeout, ConnectionRefusedError,
                    ConnectionResetError):
                self._ws = None
        return self._ws

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self._door_state == STATE_UNKNOWN:
            return None
        return self._door_state == STATE_CLOSED

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'garage'

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._supported_features is not None:
            return self._supported_features
        return super().supported_features

    @property
    def should_poll(self) -> bool:
        return True

    def close_cover(self, **kwargs):
        """Close the cover."""
        _LOGGER.info("Closing garage door " + self._device_id)
        self.send_message("doorCommand",0)
        if self._door_state == STATE_CLOSED:
            return
        else:
            self._door_state = STATE_CLOSED
            self.schedule_update_ha_state()
            return
        self._listen_cover()
        self.schedule_update_ha_state()

    def open_cover(self, **kwargs):
        """Open the cover."""
        _LOGGER.info("Opening garage door " + self._device_id)
        self.send_message("doorCommand",1)
        if self._door_state == STATE_OPEN:
            return
        else:
            self._door_state = STATE_OPEN
            self.schedule_update_ha_state()
            return
        self._listen_cover()
        self.schedule_update_ha_state()

    def _listen_cover(self):
        """Listen for changes in cover."""
        if self._unsub_listener_cover is None:
            self._unsub_listener_cover = track_utc_time_change(
                self.hass, self._time_changed_cover)

    def send_message(self, command, value):
        from websocket import _exceptions
        try:
            websocket = self.get_ws()
            if websocket is None:
                _LOGGER.error("No websocket available")
                return
            _LOGGER.debug("Calling Ryobi opening door API")
            payLoad = json.dumps({'jsonrpc': '2.0',\
                                  'method': 'gdoModuleCommand',\
                                  'params': \
                                    {'msgType': 16,\
                                     'moduleType': 5,\
                                     'portId': 7,\
                                     'moduleMsg': {command:value},\
                                     'topic':self._device_id}})
            _LOGGER.debug(payLoad)
            websocket.send(payLoad)
            payLoad = ""
            _LOGGER.debug("answer")
            result = websocket.recv()
            _LOGGER.debug(result)
        except (ConnectionRefusedError, ConnectionResetError,
                _exceptions.WebSocketTimeoutException,
                _exceptions.WebSocketProtocolException,
                _exceptions.WebSocketPayloadException,
                _exceptions.WebSocketConnectionClosedException) as e:
            _LOGGER.debug(format(e))
        self._ws = None

    def update(self):
        _LOGGER.debug("Updating RyobiGDO status")
        GDOstatus = self._get_status()
        doorState = GDOstatus['result'][0]['deviceTypeMap']\
                    ['garageDoor_7']['at']['doorState']['value']
        lightState = GDOstatus['result'][0]['deviceTypeMap']\
                    ['garageLight_7']['at']['lightState']['value']
        backupBatteryLevel = GDOstatus['result'][0]['deviceTypeMap']\
                            ['backupCharger_8']['at']['chargeLevel']['value']
        _LOGGER.info("Cover " + self._device_id + " status: doorState: "\
                    + str(doorState) + ", LightState: " + str(lightState)\
                    + ", BackupBatteryLevel: " + str(backupBatteryLevel))
        if doorState == 1:
            self._door_state = STATE_OPEN
            self.schedule_update_ha_state()
        if doorState == 0:
            self._door_state = STATE_CLOSED
            self.schedule_update_ha_state()

    def _get_status(self):
        """Get current status from Ryobi."""
        url = '{}/{}'.format(RYOBI_DEVICES_URL, self._device_id)
        resp = requests.get(url, params={
            'username': self._username,
            'password': self._password
        })
        _LOGGER.debug(resp)
        return resp.json()
