"""
Support for INSTEON PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import asyncio
import collections
import logging
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (CONF_PORT, EVENT_HOMEASSISTANT_STOP,
                                 CONF_PLATFORM)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['insteonplm==0.8.6']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'insteon_plm'

CONF_OVERRIDE = 'device_override'
CONF_ADDRESS = 'address'
CONF_CAT = 'cat'
CONF_SUBCAT = 'subcat'
CONF_FIRMWARE = 'firmware'
CONF_PRODUCT_KEY = 'product_key'

CONF_DEVICE_OVERRIDE_SCHEMA = vol.All(
    cv.deprecated(CONF_PLATFORM), vol.Schema({
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Optional(CONF_CAT): cv.byte,
        vol.Optional(CONF_SUBCAT): cv.byte,
        vol.Optional(CONF_FIRMWARE): cv.byte,
        vol.Optional(CONF_PRODUCT_KEY): cv.byte,
        vol.Optional(CONF_PLATFORM): cv.string,
        }))

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(CONF_OVERRIDE): vol.All(
            cv.ensure_list_csv, [CONF_DEVICE_OVERRIDE_SCHEMA])
        })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the connection to the PLM."""
    import insteonplm

    ipdb = IPDB()

    conf = config[DOMAIN]
    port = conf.get(CONF_PORT)
    overrides = conf.get(CONF_OVERRIDE, [])

    @callback
    def async_plm_new_device(device):
        """Detect device from transport to be delegated to platform."""
        for state_key in device.states:
            platform_info = ipdb[device.states[state_key]]
            if platform_info:
                platform = platform_info.platform
                if platform:
                    _LOGGER.info("New INSTEON PLM device: %s (%s) %s",
                                 device.address,
                                 device.states[state_key].name,
                                 platform)

                    hass.async_add_job(
                        discovery.async_load_platform(
                            hass, platform, DOMAIN,
                            discovered={'address': device.address.hex,
                                        'state_key': state_key},
                            hass_config=config))

    _LOGGER.info("Looking for PLM on %s", port)
    conn = yield from insteonplm.Connection.create(
        device=port,
        loop=hass.loop,
        workdir=hass.config.config_dir)

    plm = conn.protocol

    for device_override in overrides:
        #
        # Override the device default capabilities for a specific address
        #
        address = device_override.get('address')
        for prop in device_override:
            if prop in [CONF_CAT, CONF_SUBCAT]:
                plm.devices.add_override(address, prop,
                                         device_override[prop])
            elif prop in [CONF_FIRMWARE, CONF_PRODUCT_KEY]:
                plm.devices.add_override(address, CONF_PRODUCT_KEY,
                                         device_override[prop])

    hass.data['insteon_plm'] = plm

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, conn.close)

    plm.devices.add_device_callback(async_plm_new_device)

    return True


State = collections.namedtuple('Product', 'stateType platform')


class IPDB(object):
    """Embodies the INSTEON Product Database static data and access methods."""

    def __init__(self):
        """Create the INSTEON Product Database (IPDB)."""
        from insteonplm.states.onOff import (OnOffSwitch,
                                             OnOffSwitch_OutletTop,
                                             OnOffSwitch_OutletBottom,
                                             OpenClosedRelay)

        from insteonplm.states.dimmable import (DimmableSwitch,
                                                DimmableSwitch_Fan)

        from insteonplm.states.sensor import (VariableSensor,
                                              OnOffSensor,
                                              SmokeCO2Sensor,
                                              IoLincSensor,
                                              LeakSensorDryWet)

        self.states = [State(OnOffSwitch_OutletTop, 'switch'),
                       State(OnOffSwitch_OutletBottom, 'switch'),
                       State(OpenClosedRelay, 'switch'),
                       State(OnOffSwitch, 'switch'),

                       State(LeakSensorDryWet, 'binary_sensor'),
                       State(IoLincSensor, 'binary_sensor'),
                       State(SmokeCO2Sensor, 'sensor'),
                       State(OnOffSensor, 'binary_sensor'),
                       State(VariableSensor, 'sensor'),

                       State(DimmableSwitch_Fan, 'fan'),
                       State(DimmableSwitch, 'light')]

    def __len__(self):
        """Return the number of INSTEON state types mapped to HA platforms."""
        return len(self.states)

    def __iter__(self):
        """Itterate through the INSTEON state types to HA platforms."""
        for product in self.states:
            yield product

    def __getitem__(self, key):
        """Return a Home Assistant platform from an INSTEON state type."""
        for state in self.states:
            if isinstance(key, state.stateType):
                return state
        return None


class InsteonPLMEntity(Entity):
    """INSTEON abstract base entity."""

    def __init__(self, device, state_key):
        """Initialize the INSTEON PLM binary sensor."""
        self._insteon_device_state = device.states[state_key]
        self._insteon_device = device

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def address(self):
        """Return the address of the node."""
        return self._insteon_device.address.human

    @property
    def group(self):
        """Return the INSTEON group that the entity responds to."""
        return self._insteon_device_state.group

    @property
    def name(self):
        """Return the name of the node (used for Entity_ID)."""
        name = ''
        if self._insteon_device_state.group == 0x01:
            name = self._insteon_device.id
        else:
            name = '{:s}_{:d}'.format(self._insteon_device.id,
                                      self._insteon_device_state.group)
        return name

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        attributes = {
            'INSTEON Address': self.address,
            'INSTEON Group': self.group
        }
        return attributes

    @callback
    def async_entity_update(self, deviceid, statename, val):
        """Receive notification from transport that new data exists."""
        self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register INSTEON update events."""
        self._insteon_device_state.register_updates(
            self.async_entity_update)
