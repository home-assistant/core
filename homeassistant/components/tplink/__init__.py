"""Component to embed TP-Link smart home devices."""
import logging

from homeassistant.const import CONF_HOST
from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'tplink'

TPLINK_HOST_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string
})

CONF_LIGHT = 'light'
CONF_SWITCH = 'switch'
CONF_DISCOVERY = 'discovery'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional('light'): vol.All(cv.ensure_list, [TPLINK_HOST_SCHEMA]),
        vol.Optional('switch'): vol.All(cv.ensure_list, [TPLINK_HOST_SCHEMA]),
        vol.Optional('discovery', default=True): bool,
    }),
}, extra=vol.ALLOW_EXTRA)

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

    # Some parts of the config are optional, so we need to initialize the
    # missing ones now for async_setup_entry
    if conf is not None:
        if CONF_LIGHT not in conf:
            conf[CONF_LIGHT] = []
        if CONF_SWITCH not in conf:
            conf[CONF_SWITCH] = []
        if CONF_DISCOVERY not in conf:
            conf[CONF_DISCOVERY] = True
    else:
        conf = {'light': [], 'switch': [], 'discovery': True}

    hass.data[DOMAIN] = conf

    hass.async_create_task(hass.config_entries.flow.async_init(
        DOMAIN, context={'source': config_entries.SOURCE_IMPORT}))

    return True


async def async_setup_entry(hass, entry):
    """Set up TPLink from a config entry."""
    from pyHS100 import SmartBulb, SmartPlug, SmartDeviceException

    devices = {}

    if hass.data[DOMAIN]["discovery"]:
        devs = await _async_has_devices(hass)
        _LOGGER.info("Discovered %s TP-Link smart home device(s)", len(devs))
        devices.update(devs)

    for type_ in ['light', 'switch']:
        for entry in hass.data[DOMAIN][type_]:
            try:
                host = entry["host"]
                if type_ == 'light':
                    dev = SmartBulb(host)
                elif type_ == 'switch':
                    dev = SmartPlug(host)
                devices[host] = dev
                _LOGGER.debug("Succesfully added %s %s: %s",
                              type_, host, dev)
            except SmartDeviceException as ex:
                _LOGGER.error("Unable to initialize %s %s: %s",
                              type_, host, ex)

    def _fill_device_lists():
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

    # Avoid blocking on is_dimmable
    await hass.async_add_executor_job(_fill_device_lists)

    if hass.data[DOMAIN]['light']:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, 'light'))
    if hass.data[DOMAIN]['switch']:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, 'switch'))

    return True


config_entry_flow.register_discovery_flow(DOMAIN,
                                          'TP-Link Smart Home',
                                          _async_has_devices,
                                          config_entries.CONN_CLASS_LOCAL_POLL)
