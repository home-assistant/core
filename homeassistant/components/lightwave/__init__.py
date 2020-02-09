"""Support for device connected via Lightwave WiFi-link hub."""
from lightwave.lightwave import LWLink
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_LIGHTS, CONF_NAME, CONF_SWITCHES
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

DOMAIN = "lightwave"
LIGHTWAVE_LINK = "lightwave_link"
LIGHTWAVE_TRV_PROXY = "lightwave_proxy"
LIGHTWAVE_TRV_PROXY_PORT = "lightwave_proxy_port"
PROXY_IP = "trv_proxy_ip"
PROXY_PORT = "trv_proxy_port"


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(
                cv.has_at_least_one_key(CONF_LIGHTS, CONF_SWITCHES, "trv"),
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(PROXY_IP): cv.string,
                    vol.Optional(PROXY_PORT): cv.string,
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(CONF_LIGHTS, default={}): {
                        cv.string: vol.Schema({vol.Required(CONF_NAME): cv.string})
                    },
                    vol.Optional(CONF_SWITCHES, default={}): {
                        cv.string: vol.Schema({vol.Required(CONF_NAME): cv.string})
                    },
                    vol.Optional("trv", default={}): {
                        cv.string: vol.Schema(
                            {
                                vol.Required(CONF_NAME): cv.string,
                                vol.Required("serial"): cv.string,
                            }
                        )
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
    hass.data[LIGHTWAVE_LINK] = LWLink(host)

    trv_proxy_ip = "127.0.0.1"
    if PROXY_IP in config[DOMAIN].keys():
        trv_proxy_ip = config[DOMAIN][PROXY_IP]
    trv_proxy_port = 7878
    if PROXY_PORT in config[DOMAIN].keys():
        trv_proxy_port = int(config[DOMAIN][PROXY_PORT])

    hass.data[LIGHTWAVE_TRV_PROXY] = trv_proxy_ip
    hass.data[LIGHTWAVE_TRV_PROXY_PORT] = trv_proxy_port

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

    trvs = config[DOMAIN]["trv"]
    if trvs:
        hass.async_create_task(
            async_load_platform(hass, "climate", DOMAIN, trvs, config)
        )
        hass.async_create_task(
            async_load_platform(hass, "sensor", DOMAIN, trvs, config)
        )

    return True
