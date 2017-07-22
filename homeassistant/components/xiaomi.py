"""Support for Xiaomi Gateways."""
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.const import (ATTR_BATTERY_LEVEL, EVENT_HOMEASSISTANT_STOP,
                                 CONF_MAC)


REQUIREMENTS = ['https://github.com/Danielhiversen/PyXiaomiGateway/archive/'
                'aa9325fe6fdd62a8ef8c9ca1dce31d3292f484bb.zip#'
                'PyXiaomiGateway==0.2.0']

ATTR_GW_MAC = 'gw_mac'
ATTR_RINGTONE_ID = 'ringtone_id'
ATTR_RINGTONE_VOL = 'ringtone_vol'
CONF_DISCOVERY_RETRY = 'discovery_retry'
CONF_GATEWAYS = 'gateways'
CONF_INTERFACE = 'interface'
DOMAIN = 'xiaomi'
PY_XIAOMI_GATEWAY = "xiaomi_gw"


def _validate_conf(config):
    """Validate a list of devices definitions."""
    res_config = []
    for gw_conf in config:
        res_gw_conf = {'sid': gw_conf.get(CONF_MAC)}
        if res_gw_conf['sid'] is not None:
            res_gw_conf['sid'] = res_gw_conf['sid'].replace(":", "").lower()
            if len(res_gw_conf['sid']) != 12:
                raise vol.Invalid('Invalid mac address', gw_conf.get(CONF_MAC))
        key = gw_conf.get('key')
        if key is None:
            _LOGGER.warning(
                'Gateway Key is not provided.'
                ' Controlling gateway device will not be possible.')
        elif len(key) != 16:
            raise vol.Invalid('Invalid key %s.'
                              ' Key must be 16 characters', key)
        res_gw_conf['key'] = key
        res_config.append(res_gw_conf)
    return res_config


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_GATEWAYS, default=[{CONF_MAC: None, "key": None}]):
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

    for component in ['binary_sensor', 'sensor', 'switch', 'light', 'cover']:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    def stop_xiaomi(event):
        """Stop Xiaomi Socket."""
        _LOGGER.info("Shutting down Xiaomi Hub.")
        hass.data[PY_XIAOMI_GATEWAY].stop_listen()
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_xiaomi)

    def play_ringtone_service(call):
        """Service to play ringtone through Gateway."""
        ring_id = call.data.get(ATTR_RINGTONE_ID)
        gw_sid = call.data.get(ATTR_GW_MAC)
        if ring_id is None or gw_sid is None:
            _LOGGER.error("Mandatory parameters is not specified.")
            return

        ring_id = int(ring_id)
        if ring_id in [9, 14-19]:
            _LOGGER.error('Specified mid: %s is not defined in gateway.',
                          ring_id)
            return

        ring_vol = call.data.get(ATTR_RINGTONE_VOL)
        if ring_vol is None:
            ringtone = {'mid': ring_id}
        else:
            ringtone = {'mid': ring_id, 'vol': int(ring_vol)}

        gw_sid = gw_sid.replace(":", "").lower()

        for (_, gateway) in hass.data[PY_XIAOMI_GATEWAY].gateways.items():
            if gateway.sid == gw_sid:
                gateway.write_to_hub(gateway.sid, **ringtone)
                break
        else:
            _LOGGER.error('Unknown gateway sid: %s was specified.', gw_sid)

    def stop_ringtone_service(call):
        """Service to stop playing ringtone on Gateway."""
        gw_sid = call.data.get(ATTR_GW_MAC)
        if gw_sid is None:
            _LOGGER.error("Mandatory parameter (%s) is not specified.",
                          ATTR_GW_MAC)
            return

        gw_sid = gw_sid.replace(":", "").lower()
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
        self._write_to_hub = xiaomi_hub.write_to_hub
        self._get_from_hub = xiaomi_hub.get_from_hub
        xiaomi_hub.callbacks[self._sid].append(self.push_data)
        self._device_state_attributes = {}
        self.parse_data(device['data'])
        self.parse_voltage(device['data'])

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
