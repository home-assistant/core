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
                                 CONF_PLATFORM,
                                 CONF_ENTITY_ID)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['insteonplm==0.9.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'insteon_plm'

CONF_OVERRIDE = 'device_override'
CONF_ADDRESS = 'address'
CONF_CAT = 'cat'
CONF_SUBCAT = 'subcat'
CONF_FIRMWARE = 'firmware'
CONF_PRODUCT_KEY = 'product_key'

SRV_ADD_ALL_LINK = 'add_all_link'
SRV_DEL_ALL_LINK = 'delete_all_link'
SRV_LOAD_ALDB = 'load_all_link_database'
SRV_PRINT_ALDB = 'print_all_link_database'
SRV_PRINT_IM_ALDB = 'print_im_all_link_database'
SRV_ALL_LINK_GROUP = 'group'
SRV_ALL_LINK_MODE = 'mode'
SRV_LOAD_DB_RELOAD = 'reload'
SRV_CONTROLLER = 'controller'
SRV_RESPONDER = 'responder'

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

ADD_ALL_LINK_SCHEMA = vol.Schema({
    vol.Required(SRV_ALL_LINK_GROUP): vol.Range(min=0, max=255),
    vol.Required(SRV_ALL_LINK_MODE): vol.In([SRV_CONTROLLER, SRV_RESPONDER]),
    })

DEL_ALL_LINK_SCHEMA = vol.Schema({
    vol.Required(SRV_ALL_LINK_GROUP): vol.Range(min=0, max=255),
    })

LOAD_ALDB_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(SRV_LOAD_DB_RELOAD, default='false'): cv.boolean,
    })

PRINT_ALDB_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    })


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the connection to the PLM."""
    import insteonplm

    ipdb = IPDB()
    plm = None

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

    def add_all_link(service):
        """Add an INSTEON All-Link between two devices."""
        group = service.data.get(SRV_ALL_LINK_GROUP)
        mode = service.data.get(SRV_ALL_LINK_MODE)
        link_mode = 1 if mode.lower() == SRV_CONTROLLER else 0
        plm.start_all_linking(link_mode, group)

    def del_all_link(service):
        """Delete an INSTEON All-Link between two devices."""
        group = service.data.get(SRV_ALL_LINK_GROUP)
        plm.start_all_linking(255, group)

    def load_aldb(service):
        """Load the device All-Link database."""
        entity_id = service.data.get(CONF_ENTITY_ID)
        reload = service.data.get(SRV_LOAD_DB_RELOAD)
        entities = hass.data[DOMAIN].get('entities')
        entity = entities.get(entity_id)
        if entity:
            entity.load_aldb(reload)
        else:
            _LOGGER.error('Entity %s is not an INSTEON device', entity_id)

    def print_aldb(service):
        """Print the All-Link Database for a device."""
        # For now this sends logs to the log file.
        # Furture direction is to create an INSTEON control panel.
        entity_id = service.data.get(CONF_ENTITY_ID)
        entities = hass.data[DOMAIN].get('entities')
        entity = entities.get(entity_id)
        if entity:
            entity.print_aldb()
        else:
            _LOGGER.error('Entity %s is not an INSTEON device', entity_id)

    def print_im_aldb(service):
        """Print the All-Link Database for a device."""
        # For now this sends logs to the log file.
        # Furture direction is to create an INSTEON control panel.
        print_aldb_to_log(plm.aldb)

    def _register_services():
        hass.services.register(DOMAIN, SRV_ADD_ALL_LINK, add_all_link,
                               schema=ADD_ALL_LINK_SCHEMA)
        hass.services.register(DOMAIN, SRV_DEL_ALL_LINK, del_all_link,
                               schema=DEL_ALL_LINK_SCHEMA)
        hass.services.register(DOMAIN, SRV_LOAD_ALDB, load_aldb,
                               schema=LOAD_ALDB_SCHEMA)
        hass.services.register(DOMAIN, SRV_PRINT_ALDB, print_aldb,
                               schema=PRINT_ALDB_SCHEMA)
        hass.services.register(DOMAIN, SRV_PRINT_IM_ALDB, print_im_aldb,
                               schema=None)
        _LOGGER.debug("Insteon_plm Services registered")

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

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]['plm'] = plm
    hass.data[DOMAIN]['entities'] = {}

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, conn.close)

    plm.devices.add_device_callback(async_plm_new_device)
    hass.async_add_job(_register_services)

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
        self._insteon_device.aldb.add_loaded_callback(self._aldb_loaded)

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
        self.hass.data[DOMAIN]['entities'][self.entity_id] = self

    def load_aldb(self, reload=False):
        """Load the device All-Link Database."""
        if reload:
            self._insteon_device.aldb.clear()
        self._insteon_device.read_aldb()

    def print_aldb(self):
        """Print the device ALDB to the log file."""
        print_aldb_to_log(self._insteon_device.aldb)

    @callback
    def _aldb_loaded(self):
        """All-Link Database loaded for the device."""
        self.print_aldb()


def print_aldb_to_log(aldb):
    """Print the All-Link Database to the log file."""
    from insteonplm.devices import ALDBStatus
    _LOGGER.info('ALDB load status is %s', aldb.status.name)
    if aldb.status not in [ALDBStatus.LOADED, ALDBStatus.PARTIAL]:
        _LOGGER.warning('Device All-Link database not loaded')
        _LOGGER.warning('Use service insteon_plm.load_aldb first')
        return

    _LOGGER.info('RecID In Use Mode HWM Group Address  Data 1 Data 2 Data 3')
    _LOGGER.info('----- ------ ---- --- ----- -------- ------ ------ ------')
    for mem_addr in aldb:
        rec = aldb[mem_addr]
        # For now we write this to the log
        # Roadmap is to create a configuration panel
        in_use = 'Y' if rec.control_flags.is_in_use else 'N'
        mode = 'C' if rec.control_flags.is_controller else 'R'
        hwm = 'Y' if rec.control_flags.is_high_water_mark else 'N'
        _LOGGER.info(' {:04x}    {:s}     {:s}   {:s}    {:3d} {:s}'
                     '   {:3d}   {:3d}   {:3d}'.format(
                         rec.mem_addr, in_use, mode, hwm,
                         rec.group, rec.address.human,
                         rec.data1, rec.data2, rec.data3))
