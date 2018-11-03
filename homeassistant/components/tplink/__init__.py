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
    vol.Optional('discovery', default=True): bool,
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

    if conf is not None:
        hass.data[DOMAIN] = TPLINK_SCHEMA(conf)
    else:
        hass.data[DOMAIN] = {'light': [], 'switch': [], 'discovery': True}

    if conf is not None:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT}))

    return True


async def async_setup_entry(hass, entry):
    """Set up TPLink from a config entry."""
    from pyHS100 import SmartBulb, SmartPlug, SmartDeviceException

    devices = dict()

    if hass.data[DOMAIN]["discovery"]:
        devs = await _async_has_devices(hass)
        _LOGGER.info("Discovered %s TP-Link smart home devices", len(devs))
        devices.update(devs)

    for type_ in ['light', 'switch']:
        for entry in hass.data[DOMAIN][type_]:
            try:
                host = entry["host"]
                if type == 'light':
                    dev = SmartBulb(host)
                elif type_ == 'switch':
                    dev = SmartPlug(host)
                devices[host] = dev
                _LOGGER.debug("Succesfully added %s %s: %s",
                              type_, host, dev)
            except SmartDeviceException as ex:
                _LOGGER.error("Unable to initialize %s %s: %s",
                              type_, host, ex)

    for dev in devices.values():
        if isinstance(dev, SmartPlug):
            if dev.is_dimmable:  # Dimmers act as lights
                hass.data[DOMAIN]['light'].append(dev)
            else:
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
