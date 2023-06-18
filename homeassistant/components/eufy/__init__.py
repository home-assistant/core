"""Support for EufyHome devices."""
import lakeside
import voluptuous as vol

from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_ADDRESS,
    CONF_DEVICES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

DOMAIN = "eufy"

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Required(CONF_TYPE): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_DEVICES, default=[]): vol.All(
                    cv.ensure_list, [DEVICE_SCHEMA]
                ),
                vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
                vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = {
    "T1011": Platform.LIGHT,
    "T1012": Platform.LIGHT,
    "T1013": Platform.LIGHT,
    "T1201": Platform.SWITCH,
    "T1202": Platform.SWITCH,
    "T1203": Platform.SWITCH,
    "T1211": Platform.SWITCH,
}


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up EufyHome devices."""

    if CONF_USERNAME in config[DOMAIN] and CONF_PASSWORD in config[DOMAIN]:
        data = lakeside.get_devices(
            config[DOMAIN][CONF_USERNAME], config[DOMAIN][CONF_PASSWORD]
        )
        for device in data:
            kind = device["type"]
            if kind not in PLATFORMS:
                continue
            discovery.load_platform(hass, PLATFORMS[kind], DOMAIN, device, config)

    for device_info in config[DOMAIN][CONF_DEVICES]:
        kind = device_info["type"]
        if kind not in PLATFORMS:
            continue
        device = {}
        device["address"] = device_info["address"]
        device["code"] = device_info["access_token"]
        device["type"] = device_info["type"]
        device["name"] = device_info["name"]
        discovery.load_platform(hass, PLATFORMS[kind], DOMAIN, device, config)

    return True
