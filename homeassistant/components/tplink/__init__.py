"""Component to embed TP-Link smart home devices."""
import logging

from homeassistant.const import CONF_HOST
from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

TPLINK_HOST_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string
})

TPLINK_SCHEMA = vol.Schema({
    vol.Optional('light'): vol.All(cv.ensure_list, [TPLINK_HOST_SCHEMA]),
    vol.Optional('switch'): vol.All(cv.ensure_list, [TPLINK_HOST_SCHEMA]),
})

DOMAIN = 'tplink'
REQUIREMENTS = ['pyHS100==0.3.3']

async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    from pyHS100 import Discover

    def discover():
        devs = Discover.discover()
        return devs
    return await hass.async_add_executor_job(discover)


async def async_setup(hass, config):
    """Set up the TP-Link component."""
    conf = config.get(DOMAIN)

    _LOGGER.info("Got config from file: %s" % conf)
    if conf:
        hass.data[DOMAIN] = TPLINK_SCHEMA(conf)
    else:
        hass.data[DOMAIN] = {'light': [], 'switch': []}

    if conf is not None:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT}))

    return True


async def async_setup_entry(hass, entry):
    """Set up TPLink from a config entry."""
    from pyHS100 import SmartBulb, SmartPlug

    _LOGGER.info("async_setup_entry: %s" % entry)
    devices = await _async_has_devices(hass)
    for dev in devices.values():
        if isinstance(dev, SmartPlug):
            hass.data[DOMAIN]['switch'].append(dev)
        elif isinstance(dev, SmartBulb):
            hass.data[DOMAIN]['light'].append(dev)
        else:
            _LOGGER.error("Unknown smart device type: %s", type(dev))

    if hass.data[DOMAIN]['light']:
        hass.async_add_job(
            hass.config_entries.async_forward_entry_setup(entry, 'light'))
    if hass.data[DOMAIN]['switch']:
        hass.async_add_job(
            hass.config_entries.async_forward_entry_setup(entry, 'switch'))

    return True


config_entry_flow.register_discovery_flow(DOMAIN,
                                          'TP-Link Smart Home',
                                          _async_has_devices,
                                          config_entries.CONN_CLASS_LOCAL_POLL)
