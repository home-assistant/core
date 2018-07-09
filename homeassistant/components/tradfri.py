"""
Support for IKEA Tradfri.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ikea_tradfri/
"""
import logging
from uuid import uuid4

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import CONF_HOST
from homeassistant.components.discovery import SERVICE_IKEA_TRADFRI
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['pytradfri[async]==5.5.1']

DOMAIN = 'tradfri'
GATEWAY_IDENTITY = 'homeassistant'
CONFIG_FILE = '.tradfri_psk.conf'
KEY_CONFIG = 'tradfri_configuring'
KEY_GATEWAY = 'tradfri_gateway'
KEY_API = 'tradfri_api'
KEY_TRADFRI_GROUPS = 'tradfri_allow_tradfri_groups'
CONF_ALLOW_TRADFRI_GROUPS = 'allow_tradfri_groups'
DEFAULT_ALLOW_TRADFRI_GROUPS = True

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Inclusive(CONF_HOST, 'gateway'): cv.string,
        vol.Optional(CONF_ALLOW_TRADFRI_GROUPS,
                     default=DEFAULT_ALLOW_TRADFRI_GROUPS): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


def request_configuration(hass, config, host):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator
    hass.data.setdefault(KEY_CONFIG, {})
    instance = hass.data[KEY_CONFIG].get(host)

    # Configuration already in progress
    if instance:
        return

    async def configuration_callback(callback_data):
        """Handle the submitted configuration."""
        try:
            from pytradfri.api.aiocoap_api import APIFactory
            from pytradfri import RequestError
        except ImportError:
            _LOGGER.exception("Looks like something isn't installed!")
            return

        identity = uuid4().hex
        security_code = callback_data.get('security_code')

        api_factory = APIFactory(host, psk_id=identity, loop=hass.loop)
        # Need To Fix: currently entering a wrong security code sends
        # pytradfri aiocoap API into an endless loop.
        # Should just raise a requestError or something.
        try:
            key = await api_factory.generate_psk(security_code)
        except RequestError:
            configurator.async_notify_errors(hass, instance,
                                             "Security Code not accepted.")
            return

        res = await _setup_gateway(hass, config, host, identity, key,
                                   DEFAULT_ALLOW_TRADFRI_GROUPS)

        if not res:
            configurator.async_notify_errors(hass, instance,
                                             "Unable to connect.")
            return

        def success():
            """Set up was successful."""
            conf = load_json(hass.config.path(CONFIG_FILE))
            conf[host] = {'identity': identity,
                          'key': key}
            save_json(hass.config.path(CONFIG_FILE), conf)
            configurator.request_done(instance)

        hass.async_add_job(success)

    instance = configurator.request_config(
        "IKEA Trådfri", configuration_callback,
        description='Please enter the security code written at the bottom of '
                    'your IKEA Trådfri Gateway.',
        submit_caption="Confirm",
        fields=[{'id': 'security_code', 'name': 'Security Code',
                 'type': 'password'}]
    )


async def async_setup(hass, config):
    """Set up the Tradfri component."""
    conf = config.get(DOMAIN, {})
    host = conf.get(CONF_HOST)
    allow_tradfri_groups = conf.get(CONF_ALLOW_TRADFRI_GROUPS)
    known_hosts = await hass.async_add_job(load_json,
                                           hass.config.path(CONFIG_FILE))

    async def gateway_discovered(service, info,
                                 allow_groups=DEFAULT_ALLOW_TRADFRI_GROUPS):
        """Run when a gateway is discovered."""
        host = info['host']

        if host in known_hosts:
            # use fallbacks for old config style
            # identity was hard coded as 'homeassistant'
            identity = known_hosts[host].get('identity', 'homeassistant')
            key = known_hosts[host].get('key')
            await _setup_gateway(hass, config, host, identity, key,
                                 allow_groups)
        else:
            hass.async_add_job(request_configuration, hass, config, host)

    discovery.async_listen(hass, SERVICE_IKEA_TRADFRI, gateway_discovered)

    if host:
        await gateway_discovered(None,
                                 {'host': host},
                                 allow_tradfri_groups)
    return True


async def _setup_gateway(hass, hass_config, host, identity, key,
                         allow_tradfri_groups):
    """Create a gateway."""
    from pytradfri import Gateway, RequestError  # pylint: disable=import-error
    try:
        from pytradfri.api.aiocoap_api import APIFactory
    except ImportError:
        _LOGGER.exception("Looks like something isn't installed!")
        return False

    try:
        factory = APIFactory(host, psk_id=identity, psk=key,
                             loop=hass.loop)
        api = factory.request
        gateway = Gateway()
        gateway_info_result = await api(gateway.get_gateway_info())
    except RequestError:
        _LOGGER.exception("Tradfri setup failed.")
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
