"""Base entity for the BleBox devices integration."""

from blebox_uniapi.feature import Feature

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BleBoxCoordinator


class BleBoxEntity[_FeatureT: Feature](CoordinatorEntity[BleBoxCoordinator]):
    """Implements a common class for entities representing a BleBox feature."""

    def __init__(self, coordinator: BleBoxCoordinator, feature: _FeatureT) -> None:
        """Initialize a BleBox entity."""
        super().__init__(coordinator)
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
