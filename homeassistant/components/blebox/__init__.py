"""The BleBox devices integration."""
import asyncio
import logging

from blebox_uniapi.error import Error
from blebox_uniapi.products import Products

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["cover"]

PARALLEL_UPDATES = 0


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the BleBox devices component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up BleBox devices from a config entry."""

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

    return unload_ok


async def async_create_blebox_entities(
    api_host, async_add, entity_klass, entity_type, exception
):
    """Create entities from a BleBox product's features."""
    try:
        product = await Products.async_from_host(api_host)
    except Error as ex:
        _LOGGER.error("Identify failed at %s:%d (%s)", api_host.host, api_host.port, ex)
        raise exception from ex

    entities = []
    for feature in product.features[entity_type]:
        entities.append(entity_klass(feature))

    async_add(entities, True)
    return True


class BleBoxEntity:
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
        try:
            await self._feature.async_update()
        except Error as ex:
            _LOGGER.error("Updating '%s' failed: %s", self.name, ex)

    @property
    def device_info(self):
        """Return device information about this WLED device."""
        product = self._feature.product
        return {
            "identifiers": {(DOMAIN, product.unique_id)},
            "name": product.name,
            "manufacturer": product.brand,
            "model": product.model,
            "sw_version": product.firmware_version,
        }
