"""
Support for Ikea Tradfri.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ikea_tradfri/
"""
import asyncio
import json
import logging
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import CONF_HOST, CONF_API_KEY
from homeassistant.loader import get_component
from homeassistant.components.discovery import SERVICE_IKEA_TRADFRI

REQUIREMENTS = ['pytradfri==1.1']

DOMAIN = 'tradfri'
CONFIG_FILE = 'tradfri.conf'
KEY_CONFIG = 'tradfri_configuring'
KEY_GATEWAY = 'tradfri_gateway'
KEY_TRADFRI_GROUPS = 'tradfri_allow_tradfri_groups'
CONF_ALLOW_TRADFRI_GROUPS = 'allow_tradfri_groups'
DEFAULT_ALLOW_TRADFRI_GROUPS = True

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Inclusive(CONF_HOST, 'gateway'): cv.string,
        vol.Inclusive(CONF_API_KEY, 'gateway'): cv.string,
        vol.Optional(CONF_ALLOW_TRADFRI_GROUPS,
                     default=DEFAULT_ALLOW_TRADFRI_GROUPS): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


def request_configuration(hass, config, host):
    """Request configuration steps from the user."""
    configurator = get_component('configurator')
    hass.data.setdefault(KEY_CONFIG, {})
    instance = hass.data[KEY_CONFIG].get(host)

    # Configuration already in progress
    if instance:
        return

    @asyncio.coroutine
    def configuration_callback(callback_data):
        """Handle the submitted configuration."""
        res = yield from _setup_gateway(hass, config, host,
                                        callback_data.get('key'),
                                        DEFAULT_ALLOW_TRADFRI_GROUPS)
        if not res:
            hass.async_add_job(configurator.notify_errors, instance,
                               "Unable to connect.")
            return

        def success():
            """Set up was successful."""
            conf = _read_config(hass)
            conf[host] = {'key': callback_data.get('key')}
            _write_config(hass, conf)
            hass.async_add_job(configurator.request_done, instance)

        hass.async_add_job(success)

    instance = configurator.request_config(
        hass, "IKEA Trådfri", configuration_callback,
        description='Please enter the security code written at the bottom of '
                    'your IKEA Trådfri Gateway.',
        submit_caption="Confirm",
        fields=[{'id': 'key', 'name': 'Security Code', 'type': 'password'}]
    )


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Tradfri component."""
    conf = config.get(DOMAIN, {})
    host = conf.get(CONF_HOST)
    key = conf.get(CONF_API_KEY)
    allow_tradfri_groups = conf.get(CONF_ALLOW_TRADFRI_GROUPS)

    @asyncio.coroutine
    def gateway_discovered(service, info):
        """Run when a gateway is discovered."""
        keys = yield from hass.async_add_job(_read_config, hass)
        host = info['host']

        if host in keys:
            yield from _setup_gateway(hass, config, host, keys[host]['key'],
                                      allow_tradfri_groups)
        else:
            hass.async_add_job(request_configuration, hass, config, host)

    discovery.async_listen(hass, SERVICE_IKEA_TRADFRI, gateway_discovered)

    if host is None:
        return True

    return (yield from _setup_gateway(hass, config, host, key,
                                      allow_tradfri_groups))


@asyncio.coroutine
def _setup_gateway(hass, hass_config, host, key, allow_tradfri_groups):
    """Create a gateway."""
    from pytradfri import cli_api_factory, Gateway, RequestError, retry_timeout

    try:
        api = retry_timeout(cli_api_factory(host, key))
    except RequestError:
        return False

    gateway = Gateway(api)
    gateway_id = gateway.get_gateway_info().id
    hass.data.setdefault(KEY_GATEWAY, {})
    gateways = hass.data[KEY_GATEWAY]

    hass.data.setdefault(KEY_TRADFRI_GROUPS, {})
    tradfri_groups = hass.data[KEY_TRADFRI_GROUPS]
    tradfri_groups[gateway_id] = allow_tradfri_groups

    # Check if already set up
    if gateway_id in gateways:
        return True

    gateways[gateway_id] = gateway
    hass.async_add_job(discovery.async_load_platform(
        hass, 'light', DOMAIN, {'gateway': gateway_id}, hass_config))
    return True


def _read_config(hass):
    """Read tradfri config."""
    path = hass.config.path(CONFIG_FILE)

    if not os.path.isfile(path):
        return {}

    with open(path) as f_handle:
        # Guard against empty file
        return json.loads(f_handle.read() or '{}')


def _write_config(hass, config):
    """Write tradfri config."""
    data = json.dumps(config)
    with open(hass.config.path(CONFIG_FILE), 'w', encoding='utf-8') as outfile:
        outfile.write(data)
