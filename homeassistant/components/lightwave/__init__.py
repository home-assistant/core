"""Support for device connected via Lightwave WiFi-link hub."""

import logging

from lightwave.lightwave import LWLink
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_SWITCHES,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

CONF_SERIAL = "serial"
CONF_PROXY_IP = "proxy_ip"
CONF_PROXY_PORT = "proxy_port"
CONF_TRV = "trv"
CONF_TRVS = "trvs"
DEFAULT_PROXY_PORT = 7878
DOMAIN = "lightwave"
LIGHTWAVE_LINK = f"{DOMAIN}_link"
LIGHTWAVE_TRV_PROXY = f"{DOMAIN}_proxy"
LIGHTWAVE_TRV_PROXY_PORT = f"{DOMAIN}_proxy_port"

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(
                cv.has_at_least_one_key(CONF_LIGHTS, CONF_SWITCHES, CONF_TRV),
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(CONF_LIGHTS, default={}): {
                        cv.string: vol.Schema({vol.Required(CONF_NAME): cv.string})
                    },
                    vol.Optional(CONF_SWITCHES, default={}): {
                        cv.string: vol.Schema({vol.Required(CONF_NAME): cv.string})
                    },
                    vol.Optional(CONF_TRV, default={}): {
                        vol.Optional(
                            CONF_PROXY_PORT, default=DEFAULT_PROXY_PORT
                        ): cv.port,
                        vol.Optional(CONF_PROXY_IP): cv.string,
                        vol.Required(CONF_TRVS, default={}): {
                            cv.string: vol.Schema(
                                {
                                    vol.Required(CONF_NAME): cv.string,
                                    vol.Required(CONF_SERIAL): cv.string,
                                }
                            )
                        },
                    },
                },
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = (Platform.CLIMATE, Platform.SENSOR)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Try to start embedded Lightwave broker."""
    host = config[DOMAIN][CONF_HOST]
    lwlink = LWLink(host)
    hass.data[LIGHTWAVE_LINK] = lwlink

    if lights := config[DOMAIN][CONF_LIGHTS]:
        hass.async_create_task(
            async_load_platform(hass, Platform.LIGHT, DOMAIN, lights, config)
        )

    if switches := config[DOMAIN][CONF_SWITCHES]:
        hass.async_create_task(
            async_load_platform(hass, Platform.SWITCH, DOMAIN, switches, config)
        )

    if trv := config[DOMAIN][CONF_TRV]:
        trvs = trv[CONF_TRVS]
        proxy_ip = trv.get(CONF_PROXY_IP)
        proxy_port = trv[CONF_PROXY_PORT]
        if proxy_ip is None:
            await lwlink.LW_listen()
        else:
            lwlink.set_trv_proxy(proxy_ip, proxy_port)
            _LOGGER.warning(
                "Proxy no longer required, remove `proxy_ip` from config to use builtin listener"
            )

        for platform in PLATFORMS:
            hass.async_create_task(
                async_load_platform(hass, platform, DOMAIN, trvs, config)
            )

    return True
