"""Support for exposing Home Assistant via Zeroconf."""
import logging

import ipaddress
import voluptuous as vol

from aiozeroconf import (
    ServiceBrowser, ServiceInfo, ServiceStateChange, Zeroconf)

from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, __version__)
from homeassistant.generated import zeroconf as zeroconf_manifest

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'zeroconf'

ATTR_HOST = 'host'
ATTR_PORT = 'port'
ATTR_HOSTNAME = 'hostname'
ATTR_TYPE = 'type'
ATTR_NAME = 'name'
ATTR_PROPERTIES = 'properties'

ZEROCONF_TYPE = '_home-assistant._tcp.local.'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({}),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up Zeroconf and make Home Assistant discoverable."""
    zeroconf_name = '{}.{}'.format(hass.config.location_name, ZEROCONF_TYPE)

    params = {
        'version': __version__,
        'base_url': hass.config.api.base_url,
        # always needs authentication
        'requires_api_password': True,
    }

    info = ServiceInfo(ZEROCONF_TYPE, zeroconf_name,
                       port=hass.http.server_port, properties=params)

    zeroconf = Zeroconf(hass.loop)

    await zeroconf.register_service(info)

    async def new_service(service_type, name):
        """Signal new service discovered."""
        service_info = await zeroconf.get_service_info(service_type, name)
        info = info_from_service(service_info)
        _LOGGER.debug("Discovered new device %s %s", name, info)

        for domain in zeroconf_manifest.SERVICE_TYPES[service_type]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    domain, context={'source': DOMAIN}, data=info
                )
            )

    def service_update(_, service_type, name, state_change):
        """Service state changed."""
        if state_change is ServiceStateChange.Added:
            hass.async_create_task(new_service(service_type, name))

    for service in zeroconf_manifest.SERVICE_TYPES:
        ServiceBrowser(zeroconf, service, handlers=[service_update])

    async def stop_zeroconf(_):
        """Stop Zeroconf."""
        await zeroconf.unregister_service(info)
        await zeroconf.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_zeroconf)

    return True


def info_from_service(service):
    """Return prepared info from mDNS entries."""
    properties = {}

    for key, value in service.properties.items():
        try:
            if isinstance(value, bytes):
                value = value.decode('utf-8')
            properties[key.decode('utf-8')] = value
        except UnicodeDecodeError:
            _LOGGER.warning("Unicode decode error on %s: %s", key, value)

    address = service.address or service.address6

    info = {
        ATTR_HOST: str(ipaddress.ip_address(address)),
        ATTR_PORT: service.port,
        ATTR_HOSTNAME: service.server,
        ATTR_TYPE: service.type,
        ATTR_NAME: service.name,
        ATTR_PROPERTIES: properties,
    }

    return info
