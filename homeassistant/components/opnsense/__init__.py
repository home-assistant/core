"""Support for OPNsense Routers."""
import logging

from pyopnsense import diagnostics, routes
from pyopnsense.exceptions import APIException
import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

from .const import (
    CONF_API_SECRET,
    CONF_GATEWAY,
    CONF_TRACKER_INTERFACE,
    DOMAIN,
    OPNSENSE_DATA,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_API_SECRET): cv.string,
                vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
                vol.Optional(CONF_GATEWAY, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_TRACKER_INTERFACE, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the opnsense component."""

    conf = config[DOMAIN]
    url = conf[CONF_URL]
    api_key = conf[CONF_API_KEY]
    api_secret = conf[CONF_API_SECRET]
    verify_ssl = conf[CONF_VERIFY_SSL]
    gateways, tracker_interfaces = conf[CONF_GATEWAY], conf[CONF_TRACKER_INTERFACE]

    interfaces_client = diagnostics.InterfaceClient(
        api_key, api_secret, url, verify_ssl
    )
    gateways_client = routes.GatewayClient(api_key, api_secret, url, verify_ssl)

    try:
        interfaces_client.get_arp()
    except APIException:
        _LOGGER.exception("Failure while connecting to OPNsense API endpoint")
        return False

    hass.data[OPNSENSE_DATA] = {
        "interfaces": interfaces_client,
        "gateways": gateways_client,
        CONF_TRACKER_INTERFACE: tracker_interfaces,
    }

    if gateways:
        # Verify that specified gateways are valid
        gateways_states = gateways_client.status()["items"]
        gateways_names = [state["name"] for state in gateways_states]

        for gateway in gateways:
            if gateway not in gateways_names:
                _LOGGER.error("Specified OPNsense gateway %s is not found", gateway)
                return False

        load_platform(hass, SENSOR, DOMAIN, {CONF_GATEWAY: gateways}, config)

    if tracker_interfaces:
        # Verify that specified tracker interfaces are valid
        netinsight_client = diagnostics.NetworkInsightClient(
            api_key, api_secret, url, verify_ssl
        )
        interfaces = list(netinsight_client.get_interfaces().values())
        for interface in tracker_interfaces:
            if interface not in interfaces:
                _LOGGER.error(
                    "Specified OPNsense tracker interface %s is not found", interface
                )
                return False

        load_platform(hass, DEVICE_TRACKER, DOMAIN, tracker_interfaces, config)

    return True
