"""Support for device connected via Lightwave WiFi-link hub."""
from lightwave.lightwave import LWLink
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_LIGHTS, CONF_NAME, CONF_SWITCHES
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

CONF_SERIAL = "serial"
CONF_TRV = "trv"
CONF_TRVS = "trvs"
DEFAULT_PORT = 7878
DEFAULT_IP = "127.0.0.1"
DOMAIN = "lightwave"
LIGHTWAVE_LINK = "lightwave_link"
LIGHTWAVE_TRV_PROXY = "lightwave_proxy"
LIGHTWAVE_TRV_PROXY_PORT = "lightwave_proxy_port"
PROXY_IP = "proxy_ip"
PROXY_PORT = "proxy_port"


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
                        vol.Optional(PROXY_PORT, default=DEFAULT_PORT): cv.port,
                        vol.Optional(PROXY_IP, default=DEFAULT_IP): cv.string,
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


async def async_setup(hass, config):
    """Try to start embedded Lightwave broker."""
    host = config[DOMAIN][CONF_HOST]
    lwlink = LWLink(host)
    hass.data[LIGHTWAVE_LINK] = lwlink

    lights = config[DOMAIN][CONF_LIGHTS]
    if lights:
        hass.async_create_task(
            async_load_platform(hass, "light", DOMAIN, lights, config)
        )

    switches = config[DOMAIN][CONF_SWITCHES]
    if switches:
        hass.async_create_task(
            async_load_platform(hass, "switch", DOMAIN, switches, config)
        )

    trv = config[DOMAIN][CONF_TRV]
    trvs = trv[CONF_TRVS]
    if trv:
        proxy_ip = trv[PROXY_IP]
        proxy_port = trv[PROXY_PORT]
        hass.data[LIGHTWAVE_TRV_PROXY] = proxy_ip
        hass.data[LIGHTWAVE_TRV_PROXY_PORT] = proxy_port
        lwlink.set_trv_proxy(proxy_ip, proxy_port)
        hass.async_create_task(
            async_load_platform(hass, "climate", DOMAIN, trvs, config)
        )
        hass.async_create_task(
            async_load_platform(hass, "sensor", DOMAIN, trvs, config)
        )

    return True
