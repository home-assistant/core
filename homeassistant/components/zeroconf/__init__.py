"""Support for exposing Home Assistant via Zeroconf."""
import logging

import ipaddress
import voluptuous as vol

from homeassistant import config_entries, util
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, __version__)
from homeassistant.generated import zeroconf as manifest

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'zeroconf'

ATTR_HOST = 'host'
ATTR_PORT = 'port'
ATTR_HOSTNAME = 'hostname'
ATTR_MODEL_NUMBER = 'model_number'
ATTR_PROPERTIES = 'properties'
ATTR_MAC_ADDRESS = 'mac_address'

ZEROCONF_TYPE = '_home-assistant._tcp.local.'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({}),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up Zeroconf and make Home Assistant discoverable."""
    from aiozeroconf import Zeroconf, ServiceBrowser, ServiceInfo

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
        """"""
        service_info = await zeroconf.get_service_info(service_type, name)
        info = info_from_service(service_info)
        print(info)

        for domain in manifest.SERVICE_TYPES[service_type]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    domain,
                    context={'source': config_entries.SOURCE_DISCOVERY},
                    data=info
                )
            )

    def service_update(_, service_type, name, state_change):
        """"""
        from aiozeroconf import ServiceStateChange
        print("Service %s of type %s state changed: %s" % (
            name, service_type, state_change))

        if state_change is ServiceStateChange.Added:
            hass.async_create_task(new_service(service_type, name))

    for service in manifest.SERVICE_TYPES:
        ServiceBrowser(zeroconf, service, handlers=[service_update])

    async def stop_zeroconf(event):
        """Stop Zeroconf."""
        await zeroconf.unregister_service(info)
        await zeroconf.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_zeroconf)

    return True


def info_from_service(service):
    """Return most important info from mDNS entries."""
    properties = {}

    for key, value in service.properties.items():
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        properties[key.decode('utf-8')] = value

    address = service.address or service.address6

    info = {
        ATTR_HOST: str(ipaddress.ip_address(address)),
        ATTR_PORT: service.port,
        ATTR_HOSTNAME: service.server,
        ATTR_PROPERTIES: properties,
    }

    if "mac" in properties:
        info[ATTR_MAC_ADDRESS] = properties["mac"]

    return info
