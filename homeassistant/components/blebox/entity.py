"""Base entity for the BleBox devices integration."""

import logging

from blebox_uniapi.error import Error
from blebox_uniapi.feature import Feature

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
