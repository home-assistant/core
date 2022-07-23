"""An abstract class common to all Switchbot entities."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import MANUFACTURER
from .coordinator import SwitchbotCoordinator


class SwitchbotEntity(Entity):
    """Generic entity encapsulating common features of Switchbot device."""

    coordinator: SwitchbotCoordinator

    def __init__(
        self,
        coordinator: SwitchbotCoordinator,
        unique_id: str,
        address: str,
        name: str,
    ) -> None:
        """Initialize the entity."""
        self.coordinator = coordinator
        self._last_run_success: bool | None = None
        self._unique_id = unique_id
        self._address = address
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(bluetooth.DOMAIN, self._address)},
            manufacturer=MANUFACTURER,
            model=self.data["modelName"],
            name=name,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.available

    @property
    def data(self) -> dict[str, Any]:
        """Return coordinator data for this entity."""
        return self.coordinator.data

    @property
    def extra_state_attributes(self) -> Mapping[Any, Any]:
        """Return the state attributes."""
        return {"last_run_success": self._last_run_success}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
