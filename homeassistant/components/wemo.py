"""
Support for WeMo device discovery.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/wemo/
"""
import logging

import voluptuous as vol

from homeassistant.components.discovery import SERVICE_WEMO
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv

from homeassistant.const import EVENT_HOMEASSISTANT_STOP

REQUIREMENTS = ['pywemo==0.4.25']

DOMAIN = 'wemo'

# Mapping from Wemo model_name to component.
WEMO_MODEL_DISPATCH = {
    'Bridge':  'light',
    'CoffeeMaker': 'switch',
    'Dimmer': 'light',
    'Insight': 'switch',
    'LightSwitch': 'switch',
    'Maker':   'switch',
    'Sensor':  'binary_sensor',
    'Socket':  'switch'
}

SUBSCRIPTION_REGISTRY = None
KNOWN_DEVICES = []

_LOGGER = logging.getLogger(__name__)

CONF_STATIC = 'static'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_STATIC, default=[]): vol.Schema([cv.string])
    }),
}, extra=vol.ALLOW_EXTRA)


# pylint: disable=unused-argument, too-many-function-args
def setup(hass, config):
    """Set up for WeMo devices."""
    import pywemo

    global SUBSCRIPTION_REGISTRY
    SUBSCRIPTION_REGISTRY = pywemo.SubscriptionRegistry()
    SUBSCRIPTION_REGISTRY.start()

    def stop_wemo(event):
        """Shutdown Wemo subscriptions and subscription thread on exit."""
        _LOGGER.info("Shutting down subscriptions.")
        SUBSCRIPTION_REGISTRY.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_wemo)

    def discovery_dispatch(service, discovery_info):
        """Dispatcher for WeMo discovery events."""
        # name, model, location, mac
        model_name = discovery_info.get('model_name')
        serial = discovery_info.get('serial')

        # Only register a device once
        if serial in KNOWN_DEVICES:
            return
        _LOGGER.debug('Discovered unique device %s', serial)
        KNOWN_DEVICES.append(serial)

        component = WEMO_MODEL_DISPATCH.get(model_name, 'switch')

        discovery.load_platform(hass, component, DOMAIN, discovery_info,
                                config)

    discovery.listen(hass, SERVICE_WEMO, discovery_dispatch)

    _LOGGER.info("Scanning for WeMo devices.")
    devices = [(device.host, device) for device in pywemo.discover_devices()]

    # Add static devices from the config file.
    devices.extend((address, None)
                   for address in config.get(DOMAIN, {}).get(CONF_STATIC, []))

    for address, device in devices:
        port = pywemo.ouimeaux_device.probe_wemo(address)
        if not port:
            _LOGGER.warning('Unable to probe wemo at %s', address)
            continue
        _LOGGER.info('Adding wemo at %s:%i', address, port)

        url = 'http://%s:%i/setup.xml' % (address, port)
        if device is None:
            device = pywemo.discovery.device_from_description(url, None)

        discovery_info = {
            'model_name': device.model_name,
            'serial': device.serialnumber,
            'mac_address': device.mac,
            'ssdp_description': url,
        }

        discovery.discover(hass, SERVICE_WEMO, discovery_info)
    return True
