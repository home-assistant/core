"""Support for Homekit device discovery."""
import logging

from homeassistant.components.discovery import SERVICE_HOMEKIT
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity

from .config_flow import load_old_pairings
from .connection import get_accessory_information, HKDevice
from .const import (
    CONTROLLER, KNOWN_DEVICES
)
from .const import DOMAIN   # noqa: pylint: disable=unused-import

REQUIREMENTS = ['homekit[IP]==0.13.0']

HOMEKIT_IGNORE = [
    'BSB002',
    'Home Assistant Bridge',
    'TRADFRI gateway',
]

_LOGGER = logging.getLogger(__name__)


def escape_characteristic_name(char_name):
    """Escape any dash or dots in a characteristics name."""
    return char_name.replace('-', '_').replace('.', '_')


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

    for hkid, pairing_data in load_old_pairings(hass).items():
        controller.pairings[hkid] = IpPairing(pairing_data)

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
        HKDevice(hass, host, port, model, hkid, config_num, config)

    hass.data[KNOWN_DEVICES] = {}
    discovery.listen(hass, SERVICE_HOMEKIT, discovery_dispatch)
    return True
