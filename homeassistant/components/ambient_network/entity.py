"""Base entity class for the Ambient Weather Network integration."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AmbientNetworkDataUpdateCoordinator


class AmbientNetworkEntity(CoordinatorEntity[AmbientNetworkDataUpdateCoordinator]):
    """Entity class for Ambient network devices."""

    _attr_attribution = "Data provided by ambientnetwork.net"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AmbientNetworkDataUpdateCoordinator,
        description: EntityDescription,
        mnemonic: str,
    ) -> None:
        """Initialize the Ambient network entity."""

        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self.mnemonic = mnemonic
        self._device_id = mnemonic
        self._attr_unique_id = f"{self._device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Ambient Weather",
            name=self._device_id,
        )
        self._update_attrs()

    def _update_attrs(self) -> None:
        """Update state attributes."""

        return  # pragma: no cover

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the state."""

        self._update_attrs()  # pragma: no cover
        super()._handle_coordinator_update()  # pragma: no cover
