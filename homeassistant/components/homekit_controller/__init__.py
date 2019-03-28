"""Support for Homekit device discovery."""
import asyncio
import json
import logging
import os

from homeassistant.components.discovery import SERVICE_HOMEKIT
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import call_later

from .connection import get_accessory_information
from .const import (
    CONTROLLER, DOMAIN, HOMEKIT_ACCESSORY_DISPATCH, KNOWN_DEVICES
)


REQUIREMENTS = ['homekit[IP]==0.13.0']

HOMEKIT_DIR = '.homekit'

HOMEKIT_IGNORE = [
    'BSB002',
    'Home Assistant Bridge',
    'TRADFRI gateway',
]

_LOGGER = logging.getLogger(__name__)

RETRY_INTERVAL = 60  # seconds

PAIRING_FILE = "pairing.json"


def escape_characteristic_name(char_name):
    """Escape any dash or dots in a characteristics name."""
    return char_name.replace('-', '_').replace('.', '_')


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

        # This just tracks aid/iid pairs so we know if a HK service has been
        # mapped to a HA entity.
        self.entities = []

        self.pairing_lock = asyncio.Lock(loop=hass.loop)

        self.pairing = self.controller.pairings.get(hkid)

        if self.pairing is not None:
            self.accessory_setup()
        else:
            self.configure()

    def accessory_setup(self):
        """Handle setup of a HomeKit accessory."""
        # pylint: disable=import-error
        from homekit.model.services import ServicesTypes
        from homekit.exceptions import AccessoryDisconnectedError

        self.pairing.pairing_data['AccessoryIP'] = self.host
        self.pairing.pairing_data['AccessoryPort'] = self.port

        try:
            data = self.pairing.list_accessories_and_characteristics()
        except AccessoryDisconnectedError:
            call_later(
                self.hass, RETRY_INTERVAL, lambda _: self.accessory_setup())
            return
        for accessory in data:
            aid = accessory['aid']
            for service in accessory['services']:
                iid = service['iid']
                if (aid, iid) in self.entities:
                    # Don't add the same entity again
                    continue

                devtype = ServicesTypes.get_short(service['type'])
                _LOGGER.debug("Found %s", devtype)
                service_info = {'serial': self.hkid,
                                'aid': aid,
                                'iid': service['iid'],
                                'model': self.model,
                                'device-type': devtype}
                component = HOMEKIT_ACCESSORY_DISPATCH.get(devtype, None)
                if component is not None:
                    discovery.load_platform(self.hass, component, DOMAIN,
                                            service_info, self.config)
                    self.entities.append((aid, iid))

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

    async def get_characteristics(self, *args, **kwargs):
        """Read latest state from homekit accessory."""
        async with self.pairing_lock:
            chars = await self.hass.async_add_executor_job(
                self.pairing.get_characteristics,
                *args,
                **kwargs,
            )
        return chars

    async def put_characteristics(self, characteristics):
        """Control a HomeKit device state from Home Assistant."""
        chars = []
        for row in characteristics:
            chars.append((
                row['aid'],
                row['iid'],
                row['value'],
            ))

        async with self.pairing_lock:
            await self.hass.async_add_executor_job(
                self.pairing.put_characteristics,
                chars
            )


class HomeKitEntity(Entity):
    """Representation of a Home Assistant HomeKit device."""

    def __init__(self, accessory, devinfo):
        """Initialise a generic HomeKit device."""
        self._available = True
        self._accessory = accessory
        self._aid = devinfo['aid']
        self._iid = devinfo['iid']
        self._features = 0
        self._chars = {}
        self.setup()

    def setup(self):
        """Configure an entity baed on its HomeKit characterstics metadata."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes

        pairing_data = self._accessory.pairing.pairing_data

        get_uuid = CharacteristicsTypes.get_uuid
        characteristic_types = [
            get_uuid(c) for c in self.get_characteristic_types()
        ]

        self._chars_to_poll = []
        self._chars = {}
        self._char_names = {}

        for accessory in pairing_data.get('accessories', []):
            if accessory['aid'] != self._aid:
                continue
            self._accessory_info = get_accessory_information(accessory)
            for service in accessory['services']:
                if service['iid'] != self._iid:
                    continue
                for char in service['characteristics']:
                    try:
                        uuid = CharacteristicsTypes.get_uuid(char['type'])
                    except KeyError:
                        # If a KeyError is raised its a non-standard
                        # characteristic. We must ignore it in this case.
                        continue
                    if uuid not in characteristic_types:
                        continue
                    self._setup_characteristic(char)

    def _setup_characteristic(self, char):
        """Configure an entity based on a HomeKit characteristics metadata."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes

        # Build up a list of (aid, iid) tuples to poll on update()
        self._chars_to_poll.append((self._aid, char['iid']))

        # Build a map of ctype -> iid
        short_name = CharacteristicsTypes.get_short(char['type'])
        self._chars[short_name] = char['iid']
        self._char_names[char['iid']] = short_name

        # Callback to allow entity to configure itself based on this
        # characteristics metadata (valid values, value ranges, features, etc)
        setup_fn_name = escape_characteristic_name(short_name)
        setup_fn = getattr(self, '_setup_{}'.format(setup_fn_name), None)
        if not setup_fn:
            return
        # pylint: disable=not-callable
        setup_fn(char)

    async def async_update(self):
        """Obtain a HomeKit device's state."""
        # pylint: disable=import-error
        from homekit.exceptions import (
            AccessoryDisconnectedError, AccessoryNotFoundError)

        try:
            new_values_dict = await self._accessory.get_characteristics(
                self._chars_to_poll
            )
        except AccessoryNotFoundError:
            # Not only did the connection fail, but also the accessory is not
            # visible on the network.
            self._available = False
            return
        except AccessoryDisconnectedError:
            # Temporary connection failure. Device is still available but our
            # connection was dropped.
            return

        self._available = True

        for (_, iid), result in new_values_dict.items():
            if 'value' not in result:
                continue
            # Callback to update the entity with this characteristic value
            char_name = escape_characteristic_name(self._char_names[iid])
            update_fn = getattr(self, '_update_{}'.format(char_name), None)
            if not update_fn:
                continue
            # pylint: disable=not-callable
            update_fn(result['value'])

    @property
    def unique_id(self):
        """Return the ID of this device."""
        serial = self._accessory_info['serial-number']
        return "homekit-{}-{}".format(serial, self._iid)

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._accessory_info.get('name')

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        raise NotImplementedError


def setup(hass, config):
    """Set up for Homekit devices."""
    # pylint: disable=import-error
    import homekit
    from homekit.controller.ip_implementation import IpPairing

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
        controller.pairings[alias] = IpPairing(pairing_data)
        controller.save_data(pairing_file)

    def discovery_dispatch(service, discovery_info):
        """Dispatcher for Homekit discovery events."""
        # model, id
        host = discovery_info['host']
        port = discovery_info['port']

        # Fold property keys to lower case, making them effectively
        # case-insensitive. Some HomeKit devices capitalize them.
        properties = {
            key.lower(): value
            for (key, value) in discovery_info['properties'].items()
        }

        model = properties['md']
        hkid = properties['id']
        config_num = int(properties['c#'])

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

    hass.data[KNOWN_DEVICES] = {}
    discovery.listen(hass, SERVICE_HOMEKIT, discovery_dispatch)
    return True
