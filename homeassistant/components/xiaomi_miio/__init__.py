"""Support for Xiaomi Miio."""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_TOKEN,
)

from miio import DeviceException, gateway

from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'xiaomi_miio'

CONF_GATEWAYS = "gateways"
KEY_GATEWAY_DEVICE = "device"
KEY_GATEWAY_INFO = "info"

DEFAULT_ALARM_NAME = "Xiaomi Gateway Alarm"

GATEWAY_CONFIG = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_ALARM_NAME): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_GATEWAYS, default={}): vol.All(
                    cv.ensure_list,
                    vol.All([GATEWAY_CONFIG]),
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

def setup(hass, config):
    """Set up the Xiaomi Miio component."""
    gateways = []
    hass.data[DOMAIN] = {
        CONF_GATEWAYS: []
    }
    if DOMAIN in config:
        gateways = config[DOMAIN][CONF_GATEWAYS]

    for gw_device in gateways:
        host = gw_device.get(CONF_HOST)
        token = gw_device.get(CONF_TOKEN)
        name = gw_device.get(CONF_NAME)
        _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

        try:
            gateway_device = gateway.Gateway(host, token)
            gateway_info = gateway_device.info()
            _LOGGER.info(
                "%s %s %s detected",
                gateway_info.model,
                gateway_info.firmware_version,
                gateway_info.hardware_version,
            )

            hass.data[DOMAIN][CONF_GATEWAYS].append({CONF_NAME: name, KEY_GATEWAY_DEVICE: gateway_device, KEY_GATEWAY_INFO: gateway_info})
        except DeviceException:
            _LOGGER.error("DeviceException during setup of xiaomi gateway with host %s", host)

    for component in ["alarm_control_panel"]:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True
