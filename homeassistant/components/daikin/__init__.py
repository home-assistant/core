"""Platform for the Daikin AC."""
import asyncio
from datetime import timedelta
import logging

from aiohttp import ClientConnectionError
from async_timeout import timeout
from pydaikin.appliance import Appliance
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_HOSTS
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import Throttle

from . import config_flow  # noqa: F401
from .const import TIMEOUT

_LOGGER = logging.getLogger(__name__)

DOMAIN = "daikin"

PARALLEL_UPDATES = 0
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

COMPONENT_TYPES = ["climate", "sensor", "switch"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Optional(CONF_HOSTS, default=[]): vol.All(cv.ensure_list, [cv.string])}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Establish connection with Daikin."""
    if DOMAIN not in config:
        return True

    hosts = config[DOMAIN][CONF_HOSTS]
    if not hosts:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}
            )
        )
    for host in hosts:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: host}
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Establish connection with Daikin."""
    conf = entry.data
    daikin_api = await daikin_api_setup(hass, conf[CONF_HOST])
    if not daikin_api:
        return False
    hass.data.setdefault(DOMAIN, {}).update({entry.entry_id: daikin_api})
    for component in COMPONENT_TYPES:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await asyncio.wait(
        [
            hass.config_entries.async_forward_entry_unload(config_entry, component)
            for component in COMPONENT_TYPES
        ]
    )
    hass.data[DOMAIN].pop(config_entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return True


async def daikin_api_setup(hass, host):
    """Create a Daikin instance only once."""

    session = hass.helpers.aiohttp_client.async_get_clientsession()
    try:
        with timeout(TIMEOUT):
            device = Appliance(host, session)
            await device.init()
    except asyncio.TimeoutError:
        _LOGGER.debug("Connection to %s timed out", host)
        raise ConfigEntryNotReady
    except ClientConnectionError:
        _LOGGER.debug("ClientConnectionError to %s", host)
        raise ConfigEntryNotReady
    except Exception:  # pylint: disable=broad-except
        _LOGGER.error("Unexpected error creating device %s", host)
        return None

    api = DaikinApi(device)

    return api


class DaikinApi:
    """Keep the Daikin instance in one place and centralize the update."""

    def __init__(self, device):
        """Initialize the Daikin Handle."""
        self.device = device
        self.name = device.values["name"]
        self.ip_address = device.ip
        self._available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, **kwargs):
        """Pull the latest data from Daikin."""
        try:
            await self.device.update_status()
            self._available = True
        except ClientConnectionError:
            _LOGGER.warning("Connection failed for %s", self.ip_address)
            self._available = False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def mac(self):
        """Return mac-address of device."""
        return self.device.values.get(CONNECTION_NETWORK_MAC)

    @property
    def device_info(self):
        """Return a device description for device registry."""
        info = self.device.values
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self.mac)},
            "identifieres": self.mac,
            "manufacturer": "Daikin",
            "model": info.get("model"),
            "name": info.get("name"),
            "sw_version": info.get("ver").replace("_", "."),
        }
