"""Support for Xiaomi Gateways."""
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.const import ATTR_BATTERY_LEVEL, EVENT_HOMEASSISTANT_STOP


REQUIREMENTS = ['https://github.com/Danielhiversen/PyXiaomiGateway/archive/'
                '877faec36e1bfa4177cae2a0d4f49570af083e1d.zip#'
                'PyXiaomiGateway==0.1.0']

ATTR_RINGTONE_ID = 'ringtone_id'
ATTR_GW_SID = 'gw_sid'
ATTR_RINGTONE_VOL = 'ringtone_vol'
DOMAIN = 'xiaomi'
CONF_GATEWAYS = 'gateways'
CONF_INTERFACE = 'interface'
CONF_DISCOVERY_RETRY = 'discovery_retry'
PY_XIAOMI_GATEWAY = "xiaomi_gw"
XIAOMI_COMPONENTS = ['binary_sensor', 'sensor', 'switch', 'light', 'cover']


def _validate_conf(config):
    """Validate a list of devices definitions."""
    res_config = []
    for gw_conf in config:
        sid = gw_conf.get('sid')
        if sid is not None:
            gw_conf['sid'] = sid.replace(":", "").lower()
            if len(sid) != 12:
                raise vol.Invalid('Invalid sid %s.'
                                  ' Sid must be 12 characters', sid)
        key = gw_conf.get('key')
        if key is None:
            _LOGGER.warning(
                'Gateway Key is not provided.'
                ' Controlling gateway device will not be possible.')
        elif len(key) != 16:
            raise vol.Invalid('Invalid key %s.'
                              ' Key must be 16 characters', key)
        res_config.append(gw_conf)
    return res_config


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_GATEWAYS, default=[{"sid": None, "key": None}]):
            vol.All(cv.ensure_list, _validate_conf),
        vol.Optional(CONF_INTERFACE, default='any'): cv.string,
        vol.Optional(CONF_DISCOVERY_RETRY, default=3): cv.positive_int
    })
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Set up the Xiaomi component."""
    gateways = config[DOMAIN][CONF_GATEWAYS]
    interface = config[DOMAIN][CONF_INTERFACE]
    discovery_retry = config[DOMAIN][CONF_DISCOVERY_RETRY]

    from PyXiaomiGateway import PyXiaomiGateway
    hass.data[PY_XIAOMI_GATEWAY] = PyXiaomiGateway(hass.add_job, gateways,
                                                   interface)

    _LOGGER.debug("Expecting %s gateways", len(gateways))
    for _ in range(discovery_retry):
        _LOGGER.info('Discovering Xiaomi Gateways (Try %s)', _ + 1)
        hass.data[PY_XIAOMI_GATEWAY].discover_gateways()
        if len(hass.data[PY_XIAOMI_GATEWAY].gateways) >= len(gateways):
            break

    if not hass.data[PY_XIAOMI_GATEWAY].gateways:
        _LOGGER.error("No gateway discovered")
        return False
    hass.data[PY_XIAOMI_GATEWAY].listen()
    _LOGGER.debug("Listening for broadcast")

    for component in XIAOMI_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    def stop_xiaomi(event):
        """Stop Xiaomi Socket."""
        _LOGGER.info("Shutting down Xiaomi Hub.")
        hass.data[PY_XIAOMI_GATEWAY].stop_listen()
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_xiaomi)

    def play_ringtone_service(call):
        """Service to play ringtone through Gateway."""
        if call.data.get(ATTR_RINGTONE_ID) is None \
                or call.data.get(ATTR_GW_SID) is None:
            _LOGGER.error("Mandatory parameters is not specified.")
            return

        ring_id = int(call.data.get(ATTR_RINGTONE_ID))
        if ring_id in [9, 14-19]:
            _LOGGER.error('Specified mid: %s is not defined in gateway.',
                          ring_id)
            return

        ring_vol = call.data.get(ATTR_RINGTONE_VOL)
        if ring_vol is None:
            ringtone = {'mid': ring_id}
        else:
            ringtone = {'mid': ring_id, 'vol': int(ring_vol)}

        gw_sid = call.data.get(ATTR_GW_SID)

        for (_, gateway) in hass.data[PY_XIAOMI_GATEWAY].gateways.items():
            if gateway.sid == gw_sid:
                gateway.write_to_hub(gateway.sid, **ringtone)
                break
        else:
            _LOGGER.error('Unknown gateway sid: %s was specified.', gw_sid)

    def stop_ringtone_service(call):
        """Service to stop playing ringtone on Gateway."""
        gw_sid = call.data.get(ATTR_GW_SID)
        if gw_sid is None:
            _LOGGER.error("Mandatory parameter (%s) is not specified.",
                          ATTR_GW_SID)
            return

        for (_, gateway) in hass.data[PY_XIAOMI_GATEWAY].gateways.items():
            if gateway.sid == gw_sid:
                ringtone = {'mid': 10000}
                gateway.write_to_hub(gateway.sid, **ringtone)
                break
        else:
            _LOGGER.error('Unknown gateway sid: %s was specified.', gw_sid)

    hass.services.async_register(DOMAIN, 'play_ringtone',
                                 play_ringtone_service,
                                 description=None, schema=None)
    hass.services.async_register(DOMAIN, 'stop_ringtone',
                                 stop_ringtone_service,
                                 description=None, schema=None)
    return True


class XiaomiDevice(Entity):
    """Representation a base Xiaomi device."""

    def __init__(self, device, name, xiaomi_hub):
        """Initialize the xiaomi device."""
        self._state = None
        self._sid = device['sid']
        self._name = '{}_{}'.format(name, self._sid)
        self._device_state_attributes = {}
        self.xiaomi_hub = xiaomi_hub
        self.parse_data(device['data'])
        self.parse_voltage(device['data'])
        xiaomi_hub.callbacks[self._sid].append(self.push_data)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Poll update device status."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._device_state_attributes

    def push_data(self, data):
        """Push from Hub."""
        _LOGGER.debug("PUSH >> %s: %s", self, data)
        if self.parse_data(data) or self.parse_voltage(data):
            self.schedule_update_ha_state()

    def parse_voltage(self, data):
        """Parse battery level data sent by gateway."""
        if 'voltage' not in data:
            return False
        max_volt = 3300
        min_volt = 2800
        voltage = data['voltage']
        voltage = min(voltage, max_volt)
        voltage = max(voltage, min_volt)
        percent = ((voltage - min_volt) / (max_volt - min_volt)) * 100
        self._device_state_attributes[ATTR_BATTERY_LEVEL] = round(percent, 1)
        return True

    def parse_data(self, data):
        """Parse data sent by gateway."""
        raise NotImplementedError()
