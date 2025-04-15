"""The Evil Genius Labs integration."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EvilGeniusUpdateCoordinator


class EvilGeniusEntity(CoordinatorEntity[EvilGeniusUpdateCoordinator]):
    """Base entity for Evil Genius."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        info = self.coordinator.info
        return DeviceInfo(
            identifiers={(DOMAIN, info["wiFiChipId"])},
            connections={(dr.CONNECTION_NETWORK_MAC, info["macAddress"])},
            name=self.coordinator.device_name,
            model=self.coordinator.product_name,
            manufacturer="Evil Genius Labs",
            sw_version=info["coreVersion"].replace("_", "."),
            configuration_url=self.coordinator.client.url,
        )
