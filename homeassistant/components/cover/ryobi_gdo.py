"""
Ryobi platform for the cover component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/ryobiGDO/
"""
import logging
import json
import socket
from datetime import timedelta
import voluptuous as vol
import requests

import homeassistant.helpers.config_validation as cv
from homeassistant.components.cover import (
    CoverDevice, PLATFORM_SCHEMA, SUPPORT_OPEN, SUPPORT_CLOSE)
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

RYOBI_API_KEY_URL = "https://tti.tiwiconnect.com/api/login"
RYOBI_DEVICES_URL = "https://tti.tiwiconnect.com/api/devices"
RYOBI_WS_URL = "wss://tti.tiwiconnect.com/api/wsrpc"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Ryobi covers."""
    covers = []
    devices = config.get(CONF_COVERS)

    for device_id, device_config in devices.items():
        api_key = retrieve_api_key(device_config.get(CONF_USERNAME),
                                   device_config.get(CONF_PASSWORD),
                                   device_config.get(CONF_DEVICE, device_id))
        device_id_valid = check_device_id(device_config.get(CONF_USERNAME),
                                          device_config.get(CONF_PASSWORD),
                                          device_config.get(CONF_DEVICE,
                                                            device_id))
        if api_key is not None and device_id_valid:
            args = {
                'name': "ryobigdo_" + device_config.get(CONF_DEVICE,
                                                        device_id),
                'device_id': device_config.get(CONF_DEVICE, device_id),
                'username': device_config.get(CONF_USERNAME),
                'password': device_config.get(CONF_PASSWORD),
                'api_key': api_key
            }
            covers.append(RyobiCover(hass, args,
                                     supported_features=(SUPPORT_OPEN |
                                                         SUPPORT_CLOSE)))

    add_devices(covers)


def retrieve_api_key(username, password, device_id):
    """Getting api_key from Ryobi."""
    _LOGGER.debug("Getting api_key from Ryobi")
    req = requests.post(RYOBI_API_KEY_URL, params={
        'username': username,
        'password': password
    })
    _LOGGER.debug(req.status_code)
    if req.status_code == 200:
        _LOGGER.debug("auth OK. api_key retrieved")
        req_meta = req.json()['result']['metaData']
        local_api_key = req_meta['wskAuthAttempts'][0]['apiKey']
    else:
        _LOGGER.error("auth KO. No api_key retrieved. cover %s will\
                      not be add", str(device_id))
        local_api_key = None
    return local_api_key


def check_device_id(username, password, device_id):
    """Checking device_id from Ryobi."""
    device_found = False
    device_to_add = False
    _LOGGER.debug("Checking device_id from Ryobi")
    resp = requests.get(RYOBI_DEVICES_URL, params={
        'username': username,
        'password': password
    })
    if resp.status_code == 200:
        len_result = len(resp.json()['result'])
        if len_result == 0:
            _LOGGER.error("no device paired in your RyobiGDO account")
        else:
            _LOGGER.debug("device(s) paired in your RyobiGDO account")
            for data in resp.json()['result']:
                if data['varName'] == device_id:
                    device_found = True
    else:
        _LOGGER.error("Failed to retrieve devices information")
    if device_found is True:
        _LOGGER.info("Adding device %s to RyobiGDO Covers", device_id)
        device_to_add = True
    else:
        _LOGGER.error("Device_id %s is not among your devices.\
 It will not be add", device_id)
        device_to_add = False
    return device_to_add


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
        self._api_key = args['api_key']
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
                self._ws = self._connection((RYOBI_WS_URL), timeout=1)
                auth_mssg = json.dumps(
                    {'jsonrpc': '2.0',
                     'id': 3,
                     'method': 'srvWebSocketAuth',
                     'params': {
                         'varName': self._username,
                         'apiKey': self._api_key}})
                _LOGGER.debug(auth_mssg)
                self._ws.send(auth_mssg)
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
        """Should poll."""
        return True

    def close_cover(self, **kwargs):
        """Close the cover."""
        _LOGGER.info("Closing garage door %s", self._device_id)
        self.send_message("doorCommand", 0)
        if self._door_state == STATE_CLOSED:
            _LOGGER.debug("Door already on status closed")
        else:
            _LOGGER.debug("Changing door status to closed")
            self._door_state = STATE_CLOSED
            self.schedule_update_ha_state()
        self._listen_cover()
        self.schedule_update_ha_state()
        return

    def open_cover(self, **kwargs):
        """Open the cover."""
        _LOGGER.info("Opening garage door %s", self._device_id)
        self.send_message("doorCommand", 1)
        if self._door_state == STATE_OPEN:
            _LOGGER.debug("Door already on status open")
        else:
            _LOGGER.debug("Changing door status to open")
            self._door_state = STATE_OPEN
            self.schedule_update_ha_state()
        self._listen_cover()
        self.schedule_update_ha_state()
        return

    def _listen_cover(self):
        """Listen for changes in cover."""
        if self._unsub_listener_cover is None:
            self._unsub_listener_cover = track_utc_time_change(
                self.hass)

    def send_message(self, command, value):
        """Generic send message."""
        from websocket import _exceptions
        try:
            websocket = self.get_ws()
            if websocket is None:
                _LOGGER.error("No websocket available")
                return
            _LOGGER.debug("Calling Ryobi opening door API")
            pay_load = json.dumps({'jsonrpc': '2.0',
                                   'method': 'gdoModuleCommand',
                                   'params':
                                   {'msgType': 16,
                                    'moduleType': 5,
                                    'portId': 7,
                                    'moduleMsg': {command: value},
                                    'topic': self._device_id}})
            _LOGGER.debug(pay_load)
            websocket.send(pay_load)
            pay_load = ""
            _LOGGER.debug("answer")
            result = websocket.recv()
            _LOGGER.debug(result)
        except (ConnectionRefusedError, ConnectionResetError,
                _exceptions.WebSocketTimeoutException,
                _exceptions.WebSocketProtocolException,
                _exceptions.WebSocketPayloadException,
                _exceptions.WebSocketConnectionClosedException) as excep:
            _LOGGER.debug(format(excep))
        self._ws = None

    def update(self):
        """Update status from the door."""
        _LOGGER.debug("Updating RyobiGDO status")
        gdo_status = self._get_status()
        dtm = gdo_status['result'][0]['deviceTypeMap']
        door_state = dtm['garageDoor_7']['at']['doorState']['value']
        light_state = dtm['garageLight_7']['at']['lightState']['value']
        backup_bat_level = dtm['backupCharger_8']['at']['chargeLevel']['value']
        _LOGGER.info("Cover " + self._device_id + " status: doorState: "
                     + str(door_state) + ", LightState: " + str(light_state)
                     + ", BackupBatteryLevel: " + str(backup_bat_level))
        if door_state == 1:
            self._door_state = STATE_OPEN
            self.schedule_update_ha_state()
        if door_state == 0:
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
