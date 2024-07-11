"""The BleBox devices integration."""

import logging

from blebox_uniapi.box import Box
from blebox_uniapi.error import Error
from blebox_uniapi.feature import Feature
from blebox_uniapi.session import ApiHost

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DEFAULT_SETUP_TIMEOUT, DOMAIN, PRODUCT
from .helpers import get_maybe_authenticated_session

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BleBox devices from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    timeout = DEFAULT_SETUP_TIMEOUT

    websession = get_maybe_authenticated_session(hass, password, username)

    api_host = ApiHost(host, port, timeout, websession, hass.loop)

    try:
        product = await Box.async_from_host(api_host)
    except Error as ex:
        _LOGGER.error("Identify failed at %s:%d (%s)", api_host.host, api_host.port, ex)
        raise ConfigEntryNotReady from ex

    domain = hass.data.setdefault(DOMAIN, {})
    domain_entry = domain.setdefault(entry.entry_id, {})
    product = domain_entry.setdefault(PRODUCT, product)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class BleBoxEntity[_FeatureT: Feature](Entity):
    """Implements a common class for entities representing a BleBox feature."""

    def __init__(self, feature: _FeatureT) -> None:
        """Initialize a BleBox entity."""
        self._feature = feature
        self._attr_name = feature.full_name
        self._attr_unique_id = feature.unique_id
        product = feature.product
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, product.unique_id)},
            manufacturer=product.brand,
            model=product.model,
            name=product.name,
            sw_version=product.firmware_version,
            configuration_url=f"http://{product.address}",
        )

    async def async_update(self) -> None:
        """Update the entity state."""
        try:
            await self._feature.async_update()
        except Error as ex:
            _LOGGER.error("Updating '%s' failed: %s", self.name, ex)
