"""The BleBox devices integration."""
import asyncio
import logging

from blebox_uniapi.error import Error
from blebox_uniapi.products import Products
from blebox_uniapi.session import ApiHost

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity

from .const import DEFAULT_SETUP_TIMEOUT, DOMAIN, PRODUCT

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["cover"]

PARALLEL_UPDATES = 0


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the BleBox devices component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up BleBox devices from a config entry."""

    websession = async_get_clientsession(hass)

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    timeout = DEFAULT_SETUP_TIMEOUT

    api_host = ApiHost(host, port, timeout, websession, hass.loop)

    try:
        product = await Products.async_from_host(api_host)
    except Error as ex:
        _LOGGER.error("Identify failed at %s:%d (%s)", api_host.host, api_host.port, ex)
        raise ConfigEntryNotReady from ex

    domain = hass.data.setdefault(DOMAIN, {})
    domain_entry = domain.setdefault(entry.entry_id, {})
    product = domain_entry.setdefault(PRODUCT, product)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@callback
def create_blebox_entities(product, async_add, entity_klass, entity_type):
    """Create entities from a BleBox product's features."""

    entities = []
    if entity_type in product.features:
        for feature in product.features[entity_type]:
            entities.append(entity_klass(feature))

    async_add(entities, True)


class BleBoxEntity(Entity):
    """Implements a common class for entities representing a BleBox feature."""

    def __init__(self, feature):
        """Initialize a BleBox entity."""
        self._feature = feature

    @property
    def name(self):
        """Return the internal entity name."""
        return self._feature.full_name

    @property
    def unique_id(self):
        """Return a unique id."""
        return self._feature.unique_id

    async def async_update(self):
        """Update the entity state."""
        try:
            await self._feature.async_update()
        except Error as ex:
            _LOGGER.error("Updating '%s' failed: %s", self.name, ex)

    @property
    def device_info(self):
        """Return device information for this entity."""
        product = self._feature.product
        return {
            "identifiers": {(DOMAIN, product.unique_id)},
            "name": product.name,
            "manufacturer": product.brand,
            "model": product.model,
            "sw_version": product.firmware_version,
        }
