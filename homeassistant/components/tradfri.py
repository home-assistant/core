"""
Support for Ikea Tradfri.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ikea_tradfri/
"""
import asyncio
import json
import logging
import os
import uuid

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import CONF_HOST
from homeassistant.components.discovery import SERVICE_IKEA_TRADFRI

REQUIREMENTS = ['pytradfri==4.0.1',
                'DTLSSocket==0.1.4',
                'https://github.com/chrysn/aiocoap/archive/'
                '3286f48f0b949901c8b5c04c0719dc54ab63d431.zip'
                '#aiocoap==0.3']

DOMAIN = 'tradfri'
CONFIG_FILE = '.tradfri_identities.conf'
KEY_CONFIGURING = 'tradfri_configuring'
KEY_GATEWAY = 'tradfri_gateway'
KEY_API = 'tradfri_api'
KEY_TRADFRI_GROUPS = 'tradfri_allow_tradfri_groups'
CONF_ALLOW_TRADFRI_GROUPS = 'allow_tradfri_groups'
DEFAULT_ALLOW_TRADFRI_GROUPS = True
CONF_HOSTNAME = 'custom_hostname'
DEFAULT_HOSTNAME = 'my_Tradfri_gateway'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Inclusive(CONF_HOST, 'gateway'): cv.string,
        vol.Optional(CONF_HOSTNAME,
                     default=DEFAULT_HOSTNAME): cv.boolean,
        vol.Optional(CONF_ALLOW_TRADFRI_GROUPS,
                     default=DEFAULT_ALLOW_TRADFRI_GROUPS): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


def request_configuration(hass, config, host, hostname):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator
    hass.data.setdefault(KEY_CONFIGURING, [])

    @asyncio.coroutine
    def configuration_callback(callback_data):
        """Handle the submitted configuration."""
        try:
            from pytradfri.api.aiocoap_api import APIFactory
            from pytradfri import RequestError
        except ImportError:
            _LOGGER.exception("Looks like something isn't installed!")
            return

        # use an unique identity to pair with gateway on every config attempt
        # using the same id would make it unable to pair with a
        # new (or another) hass instance.
        identity = uuid.uuid4().hex

        api_factory = APIFactory(host, psk_id=identity, loop=hass.loop)

        # FIXME: currently entering a wrong security code sends
        # pytradfri aiocoap API into an entless loop.
        # posibly because of non standard response from gateway
        # but there's no clear Error/Exception being raised.
        # the only thing that shows up in the logs is an OSError
        try:
            token = yield from api_factory.generate_psk(
                                            callback_data.get('key'))
        except RequestError:
            hass.async_add_job(configurator.notify_errors, instance,
                               "Security Code not accepted.")
            return

        res = yield from _setup_gateway(hass, config, host, hostname,
                                        identity, token,
                                        DEFAULT_ALLOW_TRADFRI_GROUPS)
        if not res:
            hass.async_add_job(configurator.notify_errors, instance,
                               "Gateway setup failed.")
            return

        def success():
            """Set up was successful."""
            conf = _read_config(hass)
            conf[hostname] = {'host': host,
                              'identity': identity,
                              'token': token}
            _write_config(hass, conf)
            hass.async_add_job(configurator.request_done, instance)

        hass.async_add_job(success)

    # Configuration already in progress
    if host in hass.data[KEY_CONFIGURING]:
        return

    hass.data[KEY_CONFIGURING].append(host)
    instance = configurator.request_config(
        "IKEA Trådfri", configuration_callback,
        description='Please enter the security code written at the bottom of '
                    'your IKEA Trådfri Gateway.',
        submit_caption="Confirm",
        fields=[{'id': 'key', 'name': 'Security Code'}]
        )


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Tradfri component."""
    conf = config.get(DOMAIN, {})
    host = conf.get(CONF_HOST)
    hostname = conf.get(CONF_HOSTNAME)
    allow_tradfri_groups = conf.get(CONF_ALLOW_TRADFRI_GROUPS)
    known_hosts = yield from hass.async_add_job(_read_config, hass)

    @asyncio.coroutine
    def gateway_discovered(service, info):
        """Run when a gateway is discovered."""
        host = info['host']
        hostname = info['hostname']
        if hostname in known_hosts:
            yield from _setup_gateway(hass, config, host, hostname,
                                      known_hosts[host]['identity'],
                                      known_hosts[host]['token'],
                                      allow_tradfri_groups)
        else:
            hass.async_add_job(request_configuration, hass,
                               config, host, hostname)

    discovery.async_listen(hass, SERVICE_IKEA_TRADFRI, gateway_discovered)

    if host:
        yield from gateway_discovered(None,
                                      {'host': host,
                                       'hostname': hostname})

    return True


@asyncio.coroutine
def _setup_gateway(hass, hass_config, host, hostname,
                   identity, token, allow_tradfri_groups):
    """Create a gateway."""
    from pytradfri import Gateway, RequestError
    try:
        from pytradfri.api.aiocoap_api import APIFactory
    except ImportError:
        _LOGGER.exception("Looks like something isn't installed!")
        return False

    try:
        factory = APIFactory(host, psk_id=identity, psk=token, loop=hass.loop)
        api = factory.request
        gateway = Gateway()
        gateway_info_result = yield from api(gateway.get_gateway_info())
    except RequestError:
        _LOGGER.exception("Tradfri setup failed. Requesting reconfiguration.")
        hass.async_add_job(request_configuration, hass, hass_config,
                           host, hostname)
        return False

    gateway_id = gateway_info_result.id
    hass.data.setdefault(KEY_API, {})
    hass.data.setdefault(KEY_GATEWAY, {})
    gateways = hass.data[KEY_GATEWAY]
    hass.data[KEY_API][gateway_id] = api

    hass.data.setdefault(KEY_TRADFRI_GROUPS, {})
    tradfri_groups = hass.data[KEY_TRADFRI_GROUPS]
    tradfri_groups[gateway_id] = allow_tradfri_groups

    # Check if already set up
    if gateway_id in gateways:
        return True

    gateways[gateway_id] = gateway
    hass.async_add_job(discovery.async_load_platform(
        hass, 'light', DOMAIN, {'gateway': gateway_id}, hass_config))
    hass.async_add_job(discovery.async_load_platform(
        hass, 'sensor', DOMAIN, {'gateway': gateway_id}, hass_config))
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
