"""Support for OPNsense Routers."""

import logging

from aiopnsense import OPNsenseClient, OPNsenseError
import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import CONF_API_SECRET, CONF_TRACKER_INTERFACES, DOMAIN, OPNSENSE_DATA

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_API_SECRET): cv.string,
                vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
                vol.Optional(CONF_TRACKER_INTERFACES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the opnsense component."""

    conf = config[DOMAIN]
    url = conf[CONF_URL]
    api_key = conf[CONF_API_KEY]
    api_secret = conf[CONF_API_SECRET]
    verify_ssl = conf[CONF_VERIFY_SSL]
    tracker_interfaces = conf[CONF_TRACKER_INTERFACES]

    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    client = OPNsenseClient(
        url,
        api_key,
        api_secret,
        session,
        opts={"verify_ssl": verify_ssl},
        throw_errors=True,
    )

    try:
        await client.get_arp_table()
    except OPNsenseError:
        _LOGGER.exception("Failure while connecting to OPNsense API endpoint")
        return False

    interface_map: dict[str, str] = {}
    if tracker_interfaces:
        try:
            interfaces = await client.get_interfaces()
        except OPNsenseError:
            _LOGGER.exception("Failure while retrieving OPNsense network interfaces")
            return False
        interface_map = {
            iface_id: iface_data.get("name", "")
            for iface_id, iface_data in interfaces.items()
        }
        interface_names = list(interface_map.values())
        for interface in tracker_interfaces:
            if interface not in interface_names:
                _LOGGER.error(
                    "Specified OPNsense tracker interface %s is not found",
                    interface,
                )
                return False

    hass.data[OPNSENSE_DATA] = {
        "client": client,
        "interface_map": interface_map,
        CONF_TRACKER_INTERFACES: tracker_interfaces,
    }

    await async_load_platform(
        hass, Platform.DEVICE_TRACKER, DOMAIN, tracker_interfaces, config
    )
    return True
