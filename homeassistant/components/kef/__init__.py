"""The KEF Wireless Speakers component."""
from functools import partial
import ipaddress

from getmac import get_mac_address
import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

from .const import (
    CONF_INVERSE_SPEAKER_MODE,
    CONF_MAX_VOLUME,
    CONF_STANDBY_TIME,
    CONF_SUPPORTS_ON,
    CONF_VOLUME_STEP,
    DEFAULT_INVERSE_SPEAKER_MODE,
    DEFAULT_MAX_VOLUME,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SUPPORTS_ON,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)

_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TYPE): vol.In(["LS50", "LSX"]),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MAX_VOLUME, default=DEFAULT_MAX_VOLUME): cv.small_float,
        vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP): cv.small_float,
        vol.Optional(
            CONF_INVERSE_SPEAKER_MODE, default=DEFAULT_INVERSE_SPEAKER_MODE
        ): cv.boolean,
        vol.Optional(CONF_SUPPORTS_ON, default=DEFAULT_SUPPORTS_ON): cv.boolean,
        vol.Optional(CONF_STANDBY_TIME): vol.In([20, 60]),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


def get_ip_mode(host):
    """Get the 'mode' used to retrieve the MAC address."""
    try:
        if ipaddress.ip_address(host).version == 6:
            return "ip6"
        return "ip"
    except ValueError:
        return "hostname"


async def async_setup(hass, config):
    """Set up the KEF platform."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    for conf in config[DOMAIN]:
        host = conf[CONF_HOST]

        if host not in hass.data[DOMAIN]:
            hass.data[DOMAIN][host] = {}

        mode = get_ip_mode(host)
        mac = await hass.async_add_executor_job(
            partial(get_mac_address, **{mode: host})
        )
        if mac is None:
            raise PlatformNotReady("Cannot get the MAC address of KEF speaker.")

        hass.data[DOMAIN][host]["mac"] = mac

        hass.async_create_task(
            async_load_platform(hass, MEDIA_PLAYER_DOMAIN, DOMAIN, conf, config)
        )
        hass.async_create_task(
            async_load_platform(hass, SELECT_DOMAIN, DOMAIN, conf, config)
        )
        hass.async_create_task(
            async_load_platform(hass, NUMBER_DOMAIN, DOMAIN, conf, config)
        )
    return True
