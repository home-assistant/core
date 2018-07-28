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

REQUIREMENTS = ['insteonplm==0.11.7']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'insteon_plm'

CONF_OVERRIDE = 'device_override'
CONF_ADDRESS = 'address'
CONF_CAT = 'cat'
CONF_SUBCAT = 'subcat'
CONF_FIRMWARE = 'firmware'
CONF_PRODUCT_KEY = 'product_key'
CONF_X10 = 'x10_devices'
CONF_HOUSECODE = 'housecode'
CONF_UNITCODE = 'unitcode'
CONF_DIM_STEPS = 'dim_steps'
CONF_X10_ALL_UNITS_OFF = 'x10_all_units_off'
CONF_X10_ALL_LIGHTS_ON = 'x10_all_lights_on'
CONF_X10_ALL_LIGHTS_OFF = 'x10_all_lights_off'

SRV_ADD_ALL_LINK = 'add_all_link'
SRV_DEL_ALL_LINK = 'delete_all_link'
SRV_LOAD_ALDB = 'load_all_link_database'
SRV_PRINT_ALDB = 'print_all_link_database'
SRV_PRINT_IM_ALDB = 'print_im_all_link_database'
SRV_X10_ALL_UNITS_OFF = 'x10_all_units_off'
SRV_X10_ALL_LIGHTS_OFF = 'x10_all_lights_off'
SRV_X10_ALL_LIGHTS_ON = 'x10_all_lights_on'
SRV_ALL_LINK_GROUP = 'group'
SRV_ALL_LINK_MODE = 'mode'
SRV_LOAD_DB_RELOAD = 'reload'
SRV_CONTROLLER = 'controller'
SRV_RESPONDER = 'responder'
SRV_HOUSECODE = 'housecode'

HOUSECODES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h',
              'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p']

BUTTON_PRESSED_STATE_NAME = 'onLevelButton'
EVENT_BUTTON_ON = 'insteon_plm.button_on'
EVENT_BUTTON_OFF = 'insteon_plm.button_off'
EVENT_CONF_BUTTON = 'button'

CONF_DEVICE_OVERRIDE_SCHEMA = vol.All(
    cv.deprecated(CONF_PLATFORM), vol.Schema({
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Optional(CONF_CAT): cv.byte,
        vol.Optional(CONF_SUBCAT): cv.byte,
        vol.Optional(CONF_FIRMWARE): cv.byte,
        vol.Optional(CONF_PRODUCT_KEY): cv.byte,
        vol.Optional(CONF_PLATFORM): cv.string,
        }))

CONF_X10_SCHEMA = vol.All(
    vol.Schema({
        vol.Required(CONF_HOUSECODE): cv.string,
        vol.Required(CONF_UNITCODE): vol.Range(min=1, max=16),
        vol.Required(CONF_PLATFORM): cv.string,
        vol.Optional(CONF_DIM_STEPS): vol.Range(min=2, max=255)
        }))

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(CONF_OVERRIDE): vol.All(
            cv.ensure_list_csv, [CONF_DEVICE_OVERRIDE_SCHEMA]),
        vol.Optional(CONF_X10_ALL_UNITS_OFF): vol.In(HOUSECODES),
        vol.Optional(CONF_X10_ALL_LIGHTS_ON): vol.In(HOUSECODES),
        vol.Optional(CONF_X10_ALL_LIGHTS_OFF): vol.In(HOUSECODES),
        vol.Optional(CONF_X10): vol.All(
            cv.ensure_list_csv, [CONF_X10_SCHEMA])
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

X10_HOUSECODE_SCHEMA = vol.Schema({
    vol.Required(SRV_HOUSECODE): vol.In(HOUSECODES),
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
    x10_devices = conf.get(CONF_X10, [])
    x10_all_units_off_housecode = conf.get(CONF_X10_ALL_UNITS_OFF)
    x10_all_lights_on_housecode = conf.get(CONF_X10_ALL_LIGHTS_ON)
    x10_all_lights_off_housecode = conf.get(CONF_X10_ALL_LIGHTS_OFF)

    @callback
    def async_plm_new_device(device):
        """Detect device from transport to be delegated to platform."""
        for state_key in device.states:
            platform_info = ipdb[device.states[state_key]]
            if platform_info and platform_info.platform:
                platform = platform_info.platform

                if platform == 'on_off_events':
                    device.states[state_key].register_updates(
                        _fire_button_on_off_event)

                else:
                    _LOGGER.info("New INSTEON PLM device: %s (%s) %s",
                                 device.address,
                                 device.states[state_key].name,
                                 platform)

                    hass.async_create_task(
                        discovery.async_load_platform(
                            hass, platform, DOMAIN,
                            discovered={'address': device.address.id,
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

    def x10_all_units_off(service):
        """Send the X10 All Units Off command."""
        housecode = service.data.get(SRV_HOUSECODE)
        plm.x10_all_units_off(housecode)

    def x10_all_lights_off(service):
        """Send the X10 All Lights Off command."""
        housecode = service.data.get(SRV_HOUSECODE)
        plm.x10_all_lights_off(housecode)

    def x10_all_lights_on(service):
        """Send the X10 All Lights On command."""
        housecode = service.data.get(SRV_HOUSECODE)
        plm.x10_all_lights_on(housecode)

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
        hass.services.register(DOMAIN, SRV_X10_ALL_UNITS_OFF,
                               x10_all_units_off,
                               schema=X10_HOUSECODE_SCHEMA)
        hass.services.register(DOMAIN, SRV_X10_ALL_LIGHTS_OFF,
                               x10_all_lights_off,
                               schema=X10_HOUSECODE_SCHEMA)
        hass.services.register(DOMAIN, SRV_X10_ALL_LIGHTS_ON,
                               x10_all_lights_on,
                               schema=X10_HOUSECODE_SCHEMA)
        _LOGGER.debug("Insteon_plm Services registered")

    def _fire_button_on_off_event(address, group, val):
        # Firing an event when a button is pressed.
        device = plm.devices[address.hex]
        state_name = device.states[group].name
        button = ("" if state_name == BUTTON_PRESSED_STATE_NAME
                  else state_name[-1].lower())
        schema = {CONF_ADDRESS: address.hex}
        if button != "":
            schema[EVENT_CONF_BUTTON] = button
        if val:
            event = EVENT_BUTTON_ON
        else:
            event = EVENT_BUTTON_OFF
        _LOGGER.debug('Firing event %s with address %s and button %s',
                      event, address.hex, button)
        hass.bus.fire(event, schema)

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

    if x10_all_units_off_housecode:
        device = plm.add_x10_device(x10_all_units_off_housecode,
                                    20,
                                    'allunitsoff')
    if x10_all_lights_on_housecode:
        device = plm.add_x10_device(x10_all_lights_on_housecode,
                                    21,
                                    'alllightson')
    if x10_all_lights_off_housecode:
        device = plm.add_x10_device(x10_all_lights_off_housecode,
                                    22,
                                    'alllightsoff')
    for device in x10_devices:
        housecode = device.get(CONF_HOUSECODE)
        unitcode = device.get(CONF_UNITCODE)
        x10_type = 'onoff'
        steps = device.get(CONF_DIM_STEPS, 22)
        if device.get(CONF_PLATFORM) == 'light':
            x10_type = 'dimmable'
        elif device.get(CONF_PLATFORM) == 'binary_sensor':
            x10_type = 'sensor'
        _LOGGER.debug("Adding X10 device to insteonplm: %s %d %s",
                      housecode, unitcode, x10_type)
        device = plm.add_x10_device(housecode,
                                    unitcode,
                                    x10_type)
        if device and hasattr(device.states[0x01], 'steps'):
            device.states[0x01].steps = steps

    hass.async_add_job(_register_services)

    return True


State = collections.namedtuple('Product', 'stateType platform')


class IPDB:
    """Embodies the INSTEON Product Database static data and access methods."""

    def __init__(self):
        """Create the INSTEON Product Database (IPDB)."""
        from insteonplm.states.onOff import (OnOffSwitch,
                                             OnOffSwitch_OutletTop,
                                             OnOffSwitch_OutletBottom,
                                             OpenClosedRelay)

        from insteonplm.states.dimmable import (DimmableSwitch,
                                                DimmableSwitch_Fan,
                                                DimmableRemote)

        from insteonplm.states.sensor import (VariableSensor,
                                              OnOffSensor,
                                              SmokeCO2Sensor,
                                              IoLincSensor,
                                              LeakSensorDryWet)

        from insteonplm.states.x10 import (X10DimmableSwitch,
                                           X10OnOffSwitch,
                                           X10OnOffSensor,
                                           X10AllUnitsOffSensor,
                                           X10AllLightsOnSensor,
                                           X10AllLightsOffSensor)

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
                       State(DimmableSwitch, 'light'),
                       State(DimmableRemote, 'on_off_events'),

                       State(X10DimmableSwitch, 'light'),
                       State(X10OnOffSwitch, 'switch'),
                       State(X10OnOffSensor, 'binary_sensor'),
                       State(X10AllUnitsOffSensor, 'binary_sensor'),
                       State(X10AllLightsOnSensor, 'binary_sensor'),
                       State(X10AllLightsOffSensor, 'binary_sensor')]

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
