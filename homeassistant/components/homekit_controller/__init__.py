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
    # pylint: disable=import-error
    import homekit
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
        # pylint: disable=import-error
        import homekit

        _LOGGER.info("Setting up Homekit device %s", model)
        self.hass = hass
        self.host = host
        self.port = port
        self.model = model
        self.hkid = hkid
        self.config_num = config_num
        self.config = config
        self.configurator = hass.components.configurator

        data_dir = os.path.join(hass.config.path(), HOMEKIT_DIR)
        if not os.path.isdir(data_dir):
            os.mkdir(data_dir)

        self.pairing_file = os.path.join(data_dir, 'hk-{}'.format(hkid))
        self.pairing_data = homekit.load_pairing(self.pairing_file)

        # Monkey patch httpclient for increased compatibility
        # pylint: disable=protected-access
        http.client.HTTPConnection._send_output = homekit_http_send

        self.conn = http.client.HTTPConnection(self.host, port=self.port)
        if self.pairing_data is not None:
            self.accessory_setup()
        else:
            self.configure()

    def accessory_setup(self):
        """Handle setup of a HomeKit accessory."""
        # pylint: disable=import-error
        import homekit
        self.controllerkey, self.accessorykey = \
            homekit.get_session_keys(self.conn, self.pairing_data)
        self.securecon = homekit.SecureHttp(self.conn.sock,
                                            self.accessorykey,
                                            self.controllerkey)
        response = self.securecon.get('/accessories')
        data = json.loads(response.read().decode())
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

    def device_config_callback(self, callback_data):
        """Handle initial pairing."""
        # pylint: disable=import-error
        import homekit
        pairing_id = str(uuid.uuid4())
        code = callback_data.get('code').strip()
        try:
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
        self._securecon = accessory.securecon
        self._aid = devinfo['aid']
        self._iid = devinfo['iid']
        self._address = "homekit-{}-{}".format(devinfo['serial'], self._iid)
        self._features = 0
        self._chars = {}

    def update(self):
        """Obtain a HomeKit device's state."""
        response = self._securecon.get('/accessories')
        data = json.loads(response.read().decode())
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

    def update_characteristics(self, characteristics):
        """Synchronise a HomeKit device state with Home Assistant."""
        raise NotImplementedError

    def put_characteristics(self, characteristics):
        """Control a HomeKit device state from Home Assistant."""
        body = json.dumps({'characteristics': characteristics})
        self._securecon.put('/characteristics', body)


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
