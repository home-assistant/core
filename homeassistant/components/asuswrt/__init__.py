"""Support for ASUSWRT devices."""
import logging

from aioasuswrt.asuswrt import AsusWrt
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.event import async_call_later

_LOGGER = logging.getLogger(__name__)

CONF_DNSMASQ = "dnsmasq"
CONF_INTERFACE = "interface"
CONF_PUB_KEY = "pub_key"
CONF_REQUIRE_IP = "require_ip"
CONF_SENSORS = "sensors"
CONF_SSH_KEY = "ssh_key"

DOMAIN = "asuswrt"
DATA_ASUSWRT = DOMAIN

DEFAULT_SSH_PORT = 22
DEFAULT_INTERFACE = "eth0"
DEFAULT_DNSMASQ = "/var/lib/misc"

FIRST_RETRY_TIME = 60
MAX_RETRY_TIME = 900

SECRET_GROUP = "Password or SSH Key"
SENSOR_TYPES = ["upload_speed", "download_speed", "download", "upload"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PROTOCOL, default="ssh"): vol.In(["ssh", "telnet"]),
                vol.Optional(CONF_MODE, default="router"): vol.In(["router", "ap"]),
                vol.Optional(CONF_PORT, default=DEFAULT_SSH_PORT): cv.port,
                vol.Optional(CONF_REQUIRE_IP, default=True): cv.boolean,
                vol.Exclusive(CONF_PASSWORD, SECRET_GROUP): cv.string,
                vol.Exclusive(CONF_SSH_KEY, SECRET_GROUP): cv.isfile,
                vol.Exclusive(CONF_PUB_KEY, SECRET_GROUP): cv.isfile,
                vol.Optional(CONF_SENSORS): vol.All(
                    cv.ensure_list, [vol.In(SENSOR_TYPES)]
                ),
                vol.Optional(CONF_INTERFACE, default=DEFAULT_INTERFACE): cv.string,
                vol.Optional(CONF_DNSMASQ, default=DEFAULT_DNSMASQ): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config, retry_delay=FIRST_RETRY_TIME):
    """Set up the asuswrt component."""

    conf = config[DOMAIN]

    api = AsusWrt(
        conf[CONF_HOST],
        conf[CONF_PORT],
        conf[CONF_PROTOCOL] == "telnet",
        conf[CONF_USERNAME],
        conf.get(CONF_PASSWORD, ""),
        conf.get("ssh_key", conf.get("pub_key", "")),
        conf[CONF_MODE],
        conf[CONF_REQUIRE_IP],
        interface=conf[CONF_INTERFACE],
        dnsmasq=conf[CONF_DNSMASQ],
    )

    try:
        await api.connection.async_connect()
    except OSError as ex:
        _LOGGER.warning(
            "Error [%s] connecting %s to %s. Will retry in %s seconds...",
            str(ex),
            DOMAIN,
            conf[CONF_HOST],
            retry_delay,
        )

        async def retry_setup(now):
            """Retry setup if a error happens on asuswrt API."""
            await async_setup(
                hass, config, retry_delay=min(2 * retry_delay, MAX_RETRY_TIME)
            )

        async_call_later(hass, retry_delay, retry_setup)

        return True

    if not api.is_connected:
        _LOGGER.error("Error connecting %s to %s.", DOMAIN, conf[CONF_HOST])
        return False

    hass.data[DATA_ASUSWRT] = api

    hass.async_create_task(
        async_load_platform(
            hass, "sensor", DOMAIN, config[DOMAIN].get(CONF_SENSORS), config
        )
    )
    hass.async_create_task(
        async_load_platform(hass, "device_tracker", DOMAIN, {}, config)
    )

    return True
