"""Component to embed TP-Link smart home devices."""
import logging

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'tplink'
REQUIREMENTS = ['pyHS100==0.3.2']


async def async_setup(hass, config):
    """Set up the TP-Link component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}

    if conf is not None:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT}))

    return True


async def async_setup_entry(hass, entry):
    """Set up Sonos from a config entry."""
    from pyHS100 import Discover, SmartBulb, SmartPlug

    hass.data[DOMAIN] = {'light': [], 'switch': []}
    devices = await hass.async_add_executor_job(Discover.discover)
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


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    from pyHS100 import Discover

    def discover():
        devs = Discover.discover()
        return devs.values()
    return await hass.async_add_executor_job(discover)


config_entry_flow.register_discovery_flow(DOMAIN,
                                          'TP-Link Smart Home',
                                          _async_has_devices)
