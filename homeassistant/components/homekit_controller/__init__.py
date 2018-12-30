"""
Support for Homekit device discovery.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homekit_controller/
"""
import json
import logging
import os

from homeassistant.components.discovery import SERVICE_HOMEKIT
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import call_later

REQUIREMENTS = ['homekit==0.12.0']

DOMAIN = 'homekit_controller'
HOMEKIT_DIR = '.homekit'

# Mapping from Homekit type to component.
HOMEKIT_ACCESSORY_DISPATCH = {
    'lightbulb': 'light',
    'outlet': 'switch',
    'switch': 'switch',
    'thermostat': 'climate',
}

HOMEKIT_IGNORE = [
    'BSB002',
    'Home Assistant Bridge',
    'TRADFRI gateway'
]

KNOWN_ACCESSORIES = "{}-accessories".format(DOMAIN)
KNOWN_DEVICES = "{}-devices".format(DOMAIN)
CONTROLLER = "{}-controller".format(DOMAIN)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 5  # seconds
RETRY_INTERVAL = 60  # seconds

PAIRING_FILE = "pairing.json"


class HomeKitConnectionError(ConnectionError):
    """Raised when unable to connect to target device."""


def get_serial(accessory):
    """Obtain the serial number of a HomeKit device."""
    # pylint: disable=import-error
    from homekit.model.services import ServicesTypes
    from homekit.model.characteristics import CharacteristicsTypes

    for service in accessory['services']:
        if ServicesTypes.get_short(service['type']) != \
           'accessory-information':
            continue
        for characteristic in service['characteristics']:
            ctype = CharacteristicsTypes.get_short(
                characteristic['type'])
            if ctype != 'serial-number':
                continue
            return characteristic['value']
    return None


class HKDevice():
    """HomeKit device."""

    def __init__(self, hass, host, port, model, hkid, config_num, config):
        """Initialise a generic HomeKit device."""
        _LOGGER.info("Setting up Homekit device %s", model)
        self.hass = hass
        self.controller = hass.data[CONTROLLER]

        self.host = host
        self.port = port
        self.model = model
        self.hkid = hkid
        self.config_num = config_num
        self.config = config
        self.configurator = hass.components.configurator
        self._connection_warning_logged = False

        self.pairing = self.controller.pairings.get(hkid)

        if self.pairing is not None:
            self.accessory_setup()
        else:
            self.configure()

    def accessory_setup(self):
        """Handle setup of a HomeKit accessory."""
        # pylint: disable=import-error
        from homekit.model.services import ServicesTypes

        self.pairing.pairing_data['AccessoryIP'] = self.host
        self.pairing.pairing_data['AccessoryPort'] = self.port

        try:
            data = self.pairing.list_accessories_and_characteristics()
        except HomeKitConnectionError:
            call_later(
                self.hass, RETRY_INTERVAL, lambda _: self.accessory_setup())
            return
        for accessory in data:
            serial = get_serial(accessory)
            if serial in self.hass.data[KNOWN_ACCESSORIES]:
                continue
            self.hass.data[KNOWN_ACCESSORIES][serial] = self
            aid = accessory['aid']
            for service in accessory['services']:
                service_info = {'serial': serial,
                                'aid': aid,
                                'iid': service['iid']}
                devtype = ServicesTypes.get_short(service['type'])
                _LOGGER.debug("Found %s", devtype)
                component = HOMEKIT_ACCESSORY_DISPATCH.get(devtype, None)
                if component is not None:
                    discovery.load_platform(self.hass, component, DOMAIN,
                                            service_info, self.config)

    def device_config_callback(self, callback_data):
        """Handle initial pairing."""
        import homekit  # pylint: disable=import-error
        code = callback_data.get('code').strip()
        try:
            self.controller.perform_pairing(self.hkid, self.hkid, code)
        except homekit.UnavailableError:
            error_msg = "This accessory is already paired to another device. \
                         Please reset the accessory and try again."
            _configurator = self.hass.data[DOMAIN+self.hkid]
            self.configurator.notify_errors(_configurator, error_msg)
            return
        except homekit.AuthenticationError:
            error_msg = "Incorrect HomeKit code for {}. Please check it and \
                         try again.".format(self.model)
            _configurator = self.hass.data[DOMAIN+self.hkid]
            self.configurator.notify_errors(_configurator, error_msg)
            return
        except homekit.UnknownError:
            error_msg = "Received an unknown error. Please file a bug."
            _configurator = self.hass.data[DOMAIN+self.hkid]
            self.configurator.notify_errors(_configurator, error_msg)
            raise

        self.pairing = self.controller.pairings.get(self.hkid)
        if self.pairing is not None:
            pairing_file = os.path.join(
                self.hass.config.path(),
                HOMEKIT_DIR,
                PAIRING_FILE,
            )
            self.controller.save_data(pairing_file)
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
            pairing = self._accessory.pairing
            data = pairing.list_accessories_and_characteristics()
        except HomeKitConnectionError:
            return
        for accessory in data:
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
        return self._accessory.pairing is not None

    def update_characteristics(self, characteristics):
        """Synchronise a HomeKit device state with Home Assistant."""
        raise NotImplementedError

    def put_characteristics(self, characteristics):
        """Control a HomeKit device state from Home Assistant."""
        chars = []
        for row in characteristics:
            chars.append((
                row['aid'],
                row['iid'],
                row['value'],
            ))

        self._accessory.pairing.put_characteristics(chars)


def setup(hass, config):
    """Set up for Homekit devices."""
    # pylint: disable=import-error
    import homekit
    from homekit.controller import Pairing

    hass.data[CONTROLLER] = controller = homekit.Controller()

    data_dir = os.path.join(hass.config.path(), HOMEKIT_DIR)
    if not os.path.isdir(data_dir):
        os.mkdir(data_dir)

    pairing_file = os.path.join(data_dir, PAIRING_FILE)
    if os.path.exists(pairing_file):
        controller.load_data(pairing_file)

    # Migrate any existing pairings to the new internal homekit_python format
    for device in os.listdir(data_dir):
        if not device.startswith('hk-'):
            continue
        alias = device[3:]
        if alias in controller.pairings:
            continue
        with open(os.path.join(data_dir, device)) as pairing_data_fp:
            pairing_data = json.load(pairing_data_fp)
        controller.pairings[alias] = Pairing(pairing_data)
        controller.save_data(pairing_file)

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
