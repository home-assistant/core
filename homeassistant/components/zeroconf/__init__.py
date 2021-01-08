"""Support for exposing Home Assistant via Zeroconf."""
# PyLint bug confuses absolute/relative imports
# https://github.com/PyCQA/pylint/issues/1931
# pylint: disable=no-name-in-module
import logging
import socket

import ipaddress
import voluptuous as vol

from zeroconf import ServiceBrowser, ServiceInfo, ServiceStateChange, Zeroconf

from homeassistant import util
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, __version__
from homeassistant.generated.zeroconf import ZEROCONF, HOMEKIT

_LOGGER = logging.getLogger(__name__)

DOMAIN = "zeroconf"

ATTR_HOST = "host"
ATTR_PORT = "port"
ATTR_HOSTNAME = "hostname"
ATTR_TYPE = "type"
ATTR_NAME = "name"
ATTR_PROPERTIES = "properties"

ZEROCONF_TYPE = "_home-assistant._tcp.local."
HOMEKIT_TYPE = "_hap._tcp.local."

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up Zeroconf and make Home Assistant discoverable."""
    zeroconf_name = "{}.{}".format(hass.config.location_name, ZEROCONF_TYPE)

    params = {
        "version": __version__,
        "base_url": hass.config.api.base_url,
        # always needs authentication
        "requires_api_password": True,
    }

    host_ip = util.get_local_ip()

    try:
        host_ip_pton = socket.inet_pton(socket.AF_INET, host_ip)
    except socket.error:
        host_ip_pton = socket.inet_pton(socket.AF_INET6, host_ip)

    info = ServiceInfo(
        ZEROCONF_TYPE,
        zeroconf_name,
        None,
        addresses=[host_ip_pton],
        port=hass.http.server_port,
        properties=params,
    )

    zeroconf = Zeroconf()

    zeroconf.register_service(info)

    def service_update(zeroconf, service_type, name, state_change):
        """Service state changed."""
        if state_change != ServiceStateChange.Added:
            return

        service_info = zeroconf.get_service_info(service_type, name)
        info = info_from_service(service_info)
        _LOGGER.debug("Discovered new device %s %s", name, info)

        # If we can handle it as a HomeKit discovery, we do that here.
        if service_type == HOMEKIT_TYPE and handle_homekit(hass, info):
            return

        for domain in ZEROCONF[service_type]:
            hass.add_job(
                hass.config_entries.flow.async_init(
                    domain, context={"source": DOMAIN}, data=info
                )
            )

    for service in ZEROCONF:
        ServiceBrowser(zeroconf, service, handlers=[service_update])

    if HOMEKIT_TYPE not in ZEROCONF:
        ServiceBrowser(zeroconf, HOMEKIT_TYPE, handlers=[service_update])

    def stop_zeroconf(_):
        """Stop Zeroconf."""
        zeroconf.unregister_service(info)
        zeroconf.close()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_zeroconf)

    return True


def handle_homekit(hass, info) -> bool:
    """Handle a HomeKit discovery.

    Return if discovery was forwarded.
    """
    model = None
    props = info.get("properties", {})

    for key in props:
        if key.lower() == "md":
            model = props[key]
            break

    if model is None:
        return False

    for test_model in HOMEKIT:
        if model != test_model and not model.startswith(test_model + " "):
            continue

        hass.add_job(
            hass.config_entries.flow.async_init(
                HOMEKIT[test_model], context={"source": "homekit"}, data=info
            )
        )
        return True

    return False


def info_from_service(service):
    """Return prepared info from mDNS entries."""
    properties = {}

    for key, value in service.properties.items():
        try:
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            properties[key.decode("utf-8")] = value
        except UnicodeDecodeError:
            _LOGGER.warning("Unicode decode error on %s: %s", key, value)

    address = service.addresses[0]

    info = {
        ATTR_HOST: str(ipaddress.ip_address(address)),
        ATTR_PORT: service.port,
        ATTR_HOSTNAME: service.server,
        ATTR_TYPE: service.type,
        ATTR_NAME: service.name,
        ATTR_PROPERTIES: properties,
    }

    return info
