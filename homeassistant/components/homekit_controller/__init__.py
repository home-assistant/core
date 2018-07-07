"""
Support for Homekit device discovery.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homekit_controller/
"""
import http
import json
import logging
import os
import uuid

from homeassistant.components.discovery import SERVICE_HOMEKIT
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import call_later

REQUIREMENTS = ['homekit==0.10']

DOMAIN = 'homekit_controller'
HOMEKIT_DIR = '.homekit'

# Mapping from Homekit type to component.
HOMEKIT_ACCESSORY_DISPATCH = {
    'lightbulb': 'light',
    'outlet': 'switch',
    'thermostat': 'climate',
}

HOMEKIT_IGNORE = [
    'BSB002',
    'Home Assistant Bridge',
    'TRADFRI gateway'
]

KNOWN_ACCESSORIES = "{}-accessories".format(DOMAIN)
KNOWN_DEVICES = "{}-devices".format(DOMAIN)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 5  # seconds
RETRY_INTERVAL = 60  # seconds


class HomeKitConnectionError(ConnectionError):
    """Raised when unable to connect to target device."""


def homekit_http_send(self, message_body=None, encode_chunked=False):
    r"""Send the currently buffered request and clear the buffer.

    Appends an extra \r\n to the buffer.
    A message_body may be specified, to be appended to the request.
    """
    # pylint: disable=protected-access
    self._buffer.extend((b"", b""))
    msg = b"\r\n".join(self._buffer)
    del self._buffer[:]

    if message_body is not None:
        msg = msg + message_body

    self.send(msg)


def get_serial(accessory):
    """Obtain the serial number of a HomeKit device."""
    import homekit  # pylint: disable=import-error
    for service in accessory['services']:
        if homekit.ServicesTypes.get_short(service['type']) != \
           'accessory-information':
            continue
        for characteristic in service['characteristics']:
            ctype = homekit.CharacteristicsTypes.get_short(
                characteristic['type'])
            if ctype != 'serial-number':
                continue
            return characteristic['value']
    return None


class HKDevice():
    """HomeKit device."""

    def __init__(self, hass, host, port, model, hkid, config_num, config):
        """Initialise a generic HomeKit device."""
        import homekit  # pylint: disable=import-error

        _LOGGER.info("Setting up Homekit device %s", model)
        self.hass = hass
        self.host = host
        self.port = port
        self.model = model
        self.hkid = hkid
        self.config_num = config_num
        self.config = config
        self.configurator = hass.components.configurator
        self.conn = None
        self.securecon = None
        self._connection_warning_logged = False

        data_dir = os.path.join(hass.config.path(), HOMEKIT_DIR)
        if not os.path.isdir(data_dir):
            os.mkdir(data_dir)

        self.pairing_file = os.path.join(data_dir, 'hk-{}'.format(hkid))
        self.pairing_data = homekit.load_pairing(self.pairing_file)

        # Monkey patch httpclient for increased compatibility
        # pylint: disable=protected-access
        http.client.HTTPConnection._send_output = homekit_http_send

        if self.pairing_data is not None:
            self.accessory_setup()
        else:
            self.configure()

    def connect(self):
        """Open the connection to the HomeKit device."""
        # pylint: disable=import-error
        import homekit

        self.conn = http.client.HTTPConnection(
            self.host, port=self.port, timeout=REQUEST_TIMEOUT)
        if self.pairing_data is not None:
            controllerkey, accessorykey = \
                homekit.get_session_keys(self.conn, self.pairing_data)
            self.securecon = homekit.SecureHttp(
                self.conn.sock, accessorykey, controllerkey)

    def accessory_setup(self):
        """Handle setup of a HomeKit accessory."""
        import homekit  # pylint: disable=import-error

        try:
            data = self.get_json('/accessories')
        except HomeKitConnectionError:
            call_later(
                self.hass, RETRY_INTERVAL, lambda _: self.accessory_setup())
            return
        for accessory in data['accessories']:
            serial = get_serial(accessory)
            if serial in self.hass.data[KNOWN_ACCESSORIES]:
                continue
            self.hass.data[KNOWN_ACCESSORIES][serial] = self
            aid = accessory['aid']
            for service in accessory['services']:
                service_info = {'serial': serial,
                                'aid': aid,
                                'iid': service['iid']}
                devtype = homekit.ServicesTypes.get_short(service['type'])
                _LOGGER.debug("Found %s", devtype)
                component = HOMEKIT_ACCESSORY_DISPATCH.get(devtype, None)
                if component is not None:
                    discovery.load_platform(self.hass, component, DOMAIN,
                                            service_info, self.config)

    def get_json(self, target):
        """Get JSON data from the device."""
        try:
            if self.conn is None:
                self.connect()
            response = self.securecon.get(target)
            data = json.loads(response.read().decode())

            # After a successful connection, clear the warning logged status
            self._connection_warning_logged = False

            return data
        except (ConnectionError, OSError, json.JSONDecodeError) as ex:
            # Mark connection as failed
            if not self._connection_warning_logged:
                _LOGGER.warning("Failed to connect to homekit device",
                                exc_info=ex)
                self._connection_warning_logged = True
            else:
                _LOGGER.debug("Failed to connect to homekit device",
                              exc_info=ex)
            self.conn = None
            self.securecon = None
            raise HomeKitConnectionError() from ex

    def device_config_callback(self, callback_data):
        """Handle initial pairing."""
        import homekit  # pylint: disable=import-error
        pairing_id = str(uuid.uuid4())
        code = callback_data.get('code').strip()
        try:
            self.connect()
            self.pairing_data = homekit.perform_pair_setup(self.conn, code,
                                                           pairing_id)
        except homekit.exception.UnavailableError:
            error_msg = "This accessory is already paired to another device. \
                         Please reset the accessory and try again."
            _configurator = self.hass.data[DOMAIN+self.hkid]
            self.configurator.notify_errors(_configurator, error_msg)
            return
        except homekit.exception.AuthenticationError:
            error_msg = "Incorrect HomeKit code for {}. Please check it and \
                         try again.".format(self.model)
            _configurator = self.hass.data[DOMAIN+self.hkid]
            self.configurator.notify_errors(_configurator, error_msg)
            return
        except homekit.exception.UnknownError:
            error_msg = "Received an unknown error. Please file a bug."
            _configurator = self.hass.data[DOMAIN+self.hkid]
            self.configurator.notify_errors(_configurator, error_msg)
            raise

        if self.pairing_data is not None:
            homekit.save_pairing(self.pairing_file, self.pairing_data)
            _configurator = self.hass.data[DOMAIN+self.hkid]
            self.configurator.request_done(_configurator)
            self.accessory_setup()
        else:
            error_msg = "Unable to pair, please try again"
            _configurator = self.hass.data[DOMAIN+self.hkid]
            self.configurator.notify_errors(_configurator, error_msg)

    def configure(self):
        """Obtain the pairing code for a HomeKit device."""
        description = "Please enter the HomeKit code for your {}".format(
            self.model)
        self.hass.data[DOMAIN+self.hkid] = \
            self.configurator.request_config(self.model,
                                             self.device_config_callback,
                                             description=description,
                                             submit_caption="submit",
                                             fields=[{'id': 'code',
                                                      'name': 'HomeKit code',
                                                      'type': 'string'}])


class HomeKitEntity(Entity):
    """Representation of a Home Assistant HomeKit device."""

    def __init__(self, accessory, devinfo):
        """Initialise a generic HomeKit device."""
        self._name = accessory.model
        self._accessory = accessory
        self._aid = devinfo['aid']
        self._iid = devinfo['iid']
        self._address = "homekit-{}-{}".format(devinfo['serial'], self._iid)
        self._features = 0
        self._chars = {}

    def update(self):
        """Obtain a HomeKit device's state."""
        try:
            data = self._accessory.get_json('/accessories')
        except HomeKitConnectionError:
            return
        for accessory in data['accessories']:
            if accessory['aid'] != self._aid:
                continue
            for service in accessory['services']:
                if service['iid'] != self._iid:
                    continue
                self.update_characteristics(service['characteristics'])
                break

    @property
    def unique_id(self):
        """Return the ID of this device."""
        return self._address

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._accessory.conn is not None

    def update_characteristics(self, characteristics):
        """Synchronise a HomeKit device state with Home Assistant."""
        raise NotImplementedError

    def put_characteristics(self, characteristics):
        """Control a HomeKit device state from Home Assistant."""
        body = json.dumps({'characteristics': characteristics})
        self._accessory.securecon.put('/characteristics', body)


def setup(hass, config):
    """Set up for Homekit devices."""
    def discovery_dispatch(service, discovery_info):
        """Dispatcher for Homekit discovery events."""
        # model, id
        host = discovery_info['host']
        port = discovery_info['port']
        model = discovery_info['properties']['md']
        hkid = discovery_info['properties']['id']
        config_num = int(discovery_info['properties']['c#'])

        if model in HOMEKIT_IGNORE:
            return

        # Only register a device once, but rescan if the config has changed
        if hkid in hass.data[KNOWN_DEVICES]:
            device = hass.data[KNOWN_DEVICES][hkid]
            if config_num > device.config_num and \
               device.pairing_info is not None:
                device.accessory_setup()
            return

        _LOGGER.debug('Discovered unique device %s', hkid)
        device = HKDevice(hass, host, port, model, hkid, config_num, config)
        hass.data[KNOWN_DEVICES][hkid] = device

    hass.data[KNOWN_ACCESSORIES] = {}
    hass.data[KNOWN_DEVICES] = {}
    discovery.listen(hass, SERVICE_HOMEKIT, discovery_dispatch)
    return True
