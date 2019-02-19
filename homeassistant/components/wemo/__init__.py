"""Support for WeMo device discovery."""
import logging

import requests
import voluptuous as vol

from homeassistant.components.discovery import SERVICE_WEMO
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = ['pywemo==0.4.34']

DOMAIN = 'wemo'

# Mapping from Wemo model_name to component.
WEMO_MODEL_DISPATCH = {
    'Bridge':  'light',
    'CoffeeMaker': 'switch',
    'Dimmer': 'light',
    'Humidifier': 'fan',
    'Insight': 'switch',
    'LightSwitch': 'switch',
    'Maker':   'switch',
    'Motion': 'binary_sensor',
    'Sensor':  'binary_sensor',
    'Socket':  'switch',
}

SUBSCRIPTION_REGISTRY = None
KNOWN_DEVICES = []

_LOGGER = logging.getLogger(__name__)


def coerce_host_port(value):
    """Validate that provided value is either just host or host:port.

    Returns (host, None) or (host, port) respectively.
    """
    host, _, port = value.partition(':')

    if not host:
        raise vol.Invalid('host cannot be empty')

    if port:
        port = cv.port(port)
    else:
        port = None

    return host, port


CONF_STATIC = 'static'
CONF_DISCOVERY = 'discovery'

DEFAULT_DISCOVERY = True

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_STATIC, default=[]): vol.Schema([
            vol.All(cv.string, coerce_host_port)
        ]),
        vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up for WeMo devices."""
    import pywemo

    # Keep track of WeMo devices
    devices = []

    # Keep track of WeMo device subscriptions for push updates
    global SUBSCRIPTION_REGISTRY
    SUBSCRIPTION_REGISTRY = pywemo.SubscriptionRegistry()
    SUBSCRIPTION_REGISTRY.start()

    def stop_wemo(event):
        """Shutdown Wemo subscriptions and subscription thread on exit."""
        _LOGGER.debug("Shutting down WeMo event subscriptions")
        SUBSCRIPTION_REGISTRY.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_wemo)

    def setup_url_for_device(device):
        """Determine setup.xml url for given device."""
        return 'http://{}:{}/setup.xml'.format(device.host, device.port)

    def setup_url_for_address(host, port):
        """Determine setup.xml url for given host and port pair."""
        if not port:
            port = pywemo.ouimeaux_device.probe_wemo(host)

        if not port:
            return None

        return 'http://{}:{}/setup.xml'.format(host, port)

    def discovery_dispatch(service, discovery_info):
        """Dispatcher for incoming WeMo discovery events."""
        # name, model, location, mac
        model_name = discovery_info.get('model_name')
        serial = discovery_info.get('serial')

        # Only register a device once
        if serial in KNOWN_DEVICES:
            _LOGGER.debug(
                "Ignoring known device %s %s", service, discovery_info)
            return

        _LOGGER.debug("Discovered unique WeMo device: %s", serial)
        KNOWN_DEVICES.append(serial)

        component = WEMO_MODEL_DISPATCH.get(model_name, 'switch')

        discovery.load_platform(
            hass, component, DOMAIN, discovery_info, config)

    discovery.listen(hass, SERVICE_WEMO, discovery_dispatch)

    def discover_wemo_devices(now):
        """Run discovery for WeMo devices."""
        _LOGGER.debug("Beginning WeMo device discovery...")
        _LOGGER.debug("Adding statically configured WeMo devices...")
        for host, port in config.get(DOMAIN, {}).get(CONF_STATIC, []):
            url = setup_url_for_address(host, port)

            if not url:
                _LOGGER.error(
                    'Unable to get description url for WeMo at: %s',
                    '{}:{}'.format(host, port) if port else host)
                continue

            try:
                device = pywemo.discovery.device_from_description(url, None)
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as err:
                _LOGGER.error("Unable to access WeMo at %s (%s)", url, err)
                continue

            if not [d[1] for d in devices
                    if d[1].serialnumber == device.serialnumber]:
                devices.append((url, device))

        if config.get(DOMAIN, {}).get(CONF_DISCOVERY):
            _LOGGER.debug("Scanning network for WeMo devices...")
            for device in pywemo.discover_devices():
                if not [d[1] for d in devices
                        if d[1].serialnumber == device.serialnumber]:
                    devices.append((setup_url_for_device(device),
                                    device))

        for url, device in devices:
            _LOGGER.debug(
                "Adding WeMo device at %s:%i", device.host, device.port)

            discovery_info = {
                'model_name': device.model_name,
                'serial': device.serialnumber,
                'mac_address': device.mac,
                'ssdp_description': url,
            }

            discovery.discover(hass, SERVICE_WEMO, discovery_info)

        _LOGGER.debug("WeMo device discovery has finished")

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, discover_wemo_devices)

    return True
