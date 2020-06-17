"""Support for exposing Home Assistant via Zeroconf."""
import asyncio
import ipaddress
import logging
import socket

import voluptuous as vol
from zeroconf import (
    DNSPointer,
    DNSRecord,
    InterfaceChoice,
    NonUniqueNameException,
    ServiceBrowser,
    ServiceInfo,
    ServiceStateChange,
    Zeroconf,
    log as zeroconf_log,
)

from homeassistant import util
from homeassistant.const import (
    ATTR_NAME,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    __version__,
)
from homeassistant.generated.zeroconf import HOMEKIT, ZEROCONF
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.singleton import singleton

_LOGGER = logging.getLogger(__name__)

DOMAIN = "zeroconf"

ATTR_HOST = "host"
ATTR_PORT = "port"
ATTR_HOSTNAME = "hostname"
ATTR_TYPE = "type"
ATTR_PROPERTIES = "properties"

ZEROCONF_TYPE = "_home-assistant._tcp.local."
HOMEKIT_TYPE = "_hap._tcp.local."

CONF_DEFAULT_INTERFACE = "default_interface"
DEFAULT_DEFAULT_INTERFACE = False

HOMEKIT_PROPERTIES = "properties"
HOMEKIT_PAIRED_STATUS_FLAG = "sf"
HOMEKIT_MODEL = "md"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(
                    CONF_DEFAULT_INTERFACE, default=DEFAULT_DEFAULT_INTERFACE
                ): cv.boolean
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@singleton(DOMAIN)
async def async_get_instance(hass):
    """Zeroconf instance to be shared with other integrations that use it."""
    return await hass.async_add_executor_job(_get_instance, hass)


def _get_instance(hass, default_interface=False):
    """Create an instance."""
    args = [InterfaceChoice.Default] if default_interface else []
    zeroconf = HaZeroconf(*args)

    def stop_zeroconf(_):
        """Stop Zeroconf."""
        zeroconf.ha_close()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_zeroconf)

    return zeroconf


class HaServiceBrowser(ServiceBrowser):
    """ServiceBrowser that only consumes DNSPointer records."""

    def update_record(self, zc: "Zeroconf", now: float, record: DNSRecord) -> None:
        """Pre-Filter update_record to DNSPointers for the configured type."""

        #
        # Each ServerBrowser currently runs in its own thread which
        # processes every A or AAAA record update per instance.
        #
        # As the list of zeroconf names we watch for grows, each additional
        # ServiceBrowser would process all the A and AAAA updates on the network.
        #
        # To avoid overwhemling the system we pre-filter here and only process
        # DNSPointers for the configured record name (type)
        #
        if record.name not in self.types or not isinstance(record, DNSPointer):
            return
        super().update_record(zc, now, record)


class HaZeroconf(Zeroconf):
    """Zeroconf that cannot be closed."""

    def close(self):
        """Fake method to avoid integrations closing it."""

    ha_close = Zeroconf.close


def setup(hass, config):
    """Set up Zeroconf and make Home Assistant discoverable."""
    # Zeroconf sets its log level to WARNING, reset it to allow filtering by the logger component.
    zeroconf_log.setLevel(logging.NOTSET)
    zeroconf = hass.data[DOMAIN] = _get_instance(
        hass, config.get(DOMAIN, {}).get(CONF_DEFAULT_INTERFACE)
    )

    # Get instance UUID
    uuid = asyncio.run_coroutine_threadsafe(
        hass.helpers.instance_id.async_get(), hass.loop
    ).result()

    params = {
        "location_name": hass.config.location_name,
        "uuid": uuid,
        "version": __version__,
        "external_url": "",
        "internal_url": "",
        # Old base URL, for backward compatibility
        "base_url": "",
        # Always needs authentication
        "requires_api_password": True,
    }

    # Get instance URL's
    try:
        params["external_url"] = get_url(hass, allow_internal=False)
    except NoURLAvailableError:
        pass

    try:
        params["internal_url"] = get_url(hass, allow_external=False)
    except NoURLAvailableError:
        pass

    # Set old base URL based on external or internal
    params["base_url"] = params["external_url"] or params["internal_url"]

    host_ip = util.get_local_ip()

    try:
        host_ip_pton = socket.inet_pton(socket.AF_INET, host_ip)
    except OSError:
        host_ip_pton = socket.inet_pton(socket.AF_INET6, host_ip)

    info = ServiceInfo(
        ZEROCONF_TYPE,
        name=f"{hass.config.location_name}.{ZEROCONF_TYPE}",
        server=f"{uuid}.local.",
        addresses=[host_ip_pton],
        port=hass.http.server_port,
        properties=params,
    )

    def zeroconf_hass_start(_event):
        """Expose Home Assistant on zeroconf when it starts.

        Wait till started or otherwise HTTP is not up and running.
        """
        _LOGGER.info("Starting Zeroconf broadcast")
        try:
            zeroconf.register_service(info)
        except NonUniqueNameException:
            _LOGGER.error(
                "Home Assistant instance with identical name present in the local network"
            )

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, zeroconf_hass_start)

    def service_update(zeroconf, service_type, name, state_change):
        """Service state changed."""
        if state_change != ServiceStateChange.Added:
            return

        service_info = zeroconf.get_service_info(service_type, name)
        if not service_info:
            # Prevent the browser thread from collapsing as
            # service_info can be None
            _LOGGER.debug("Failed to get info for device %s", name)
            return

        info = info_from_service(service_info)
        _LOGGER.debug("Discovered new device %s %s", name, info)

        # If we can handle it as a HomeKit discovery, we do that here.
        if service_type == HOMEKIT_TYPE:
            handle_homekit(hass, info)
            # Continue on here as homekit_controller
            # still needs to get updates on devices
            # so it can see when the 'c#' field is updated.
            #
            # We only send updates to homekit_controller
            # if the device is already paired in order to avoid
            # offering a second discovery for the same device
            if (
                HOMEKIT_PROPERTIES in info
                and HOMEKIT_PAIRED_STATUS_FLAG in info[HOMEKIT_PROPERTIES]
            ):
                try:
                    # 0 means paired and not discoverable by iOS clients)
                    if int(info[HOMEKIT_PROPERTIES][HOMEKIT_PAIRED_STATUS_FLAG]):
                        return
                except ValueError:
                    # HomeKit pairing status unknown
                    # likely bad homekit data
                    return

        for domain in ZEROCONF[service_type]:
            hass.add_job(
                hass.config_entries.flow.async_init(
                    domain, context={"source": DOMAIN}, data=info
                )
            )

    types = list(ZEROCONF)

    if HOMEKIT_TYPE not in ZEROCONF:
        types.append(HOMEKIT_TYPE)

    HaServiceBrowser(zeroconf, types, handlers=[service_update])

    return True


def handle_homekit(hass, info) -> bool:
    """Handle a HomeKit discovery.

    Return if discovery was forwarded.
    """
    model = None
    props = info.get(HOMEKIT_PROPERTIES, {})

    for key in props:
        if key.lower() == HOMEKIT_MODEL:
            model = props[key]
            break

    if model is None:
        return False

    for test_model in HOMEKIT:
        if (
            model != test_model
            and not model.startswith(f"{test_model} ")
            and not model.startswith(f"{test_model}-")
        ):
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
    properties = {"_raw": {}}

    for key, value in service.properties.items():
        # See https://ietf.org/rfc/rfc6763.html#section-6.4 and
        # https://ietf.org/rfc/rfc6763.html#section-6.5 for expected encodings
        # for property keys and values
        try:
            key = key.decode("ascii")
        except UnicodeDecodeError:
            _LOGGER.debug(
                "Ignoring invalid key provided by [%s]: %s", service.name, key
            )
            continue

        properties["_raw"][key] = value

        try:
            if isinstance(value, bytes):
                properties[key] = value.decode("utf-8")
        except UnicodeDecodeError:
            pass

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
