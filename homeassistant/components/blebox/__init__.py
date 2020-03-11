"""The BleBox devices integration."""
import asyncio
import logging

from blebox_uniapi.products import Products
from blebox_uniapi.session import ApiHost
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["sensor", "cover", "air_quality", "light", "climate", "switch"]


# TODO: test
async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the BleBox devices component."""
    # TODO: coverage
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up BleBox devices from a config entry."""

    # TODO: coverage
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    # TODO: coverage
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    return unload_ok


async def async_add_blebox(klass, method, hass, config, async_add):
    """Add a BleBox device from the given config."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    timeout = config.get(CONF_TIMEOUT)

    websession = async_get_clientsession(hass)
    api_host = ApiHost(host, port, timeout, websession, hass.loop, _LOGGER)
    # TODO: handle exceptions here (CannotConnect?)
    product = await Products.async_from_host(api_host)

    entities = []
    for entity in product.features[method]:
        entities.append(klass(entity))

    async_add(entities, True)
    return True


class CommonEntity:
    """Implements methods common among BleBox entities."""

    def __init__(self, feature):
        """Initialize the cover entity."""
        self._feature = feature

    @property
    def name(self):
        """Return the name."""
        return self._feature.full_name

    @property
    def unique_id(self):
        """Return a unique id."""
        return self._feature.unique_id

    async def async_update(self):
        """Update the cover state."""
        await self._feature.async_update()
