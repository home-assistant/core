"""The Nibe Heat Pump coordinator."""

from __future__ import annotations

from nibe.coil import Coil, CoilData

from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import CoilCoordinator


class CoilEntity(CoordinatorEntity[CoilCoordinator]):
    """Base for coil based entities."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: CoilCoordinator, coil: Coil, entity_format: str
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator, {coil.address})
        self.entity_id = async_generate_entity_id(
            entity_format, coil.name, hass=coordinator.hass
        )
        self._attr_name = coil.title
        self._attr_unique_id = f"{coordinator.unique_id}-{coil.address}"
        self._attr_device_info = coordinator.device_info
        self._coil = coil

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._coil.address in (
            self.coordinator.data or {}
        )

    def _async_read_coil(self, data: CoilData):
        """Update state of entity based on coil data."""

    async def _async_write_coil(self, value: float | str):
        """Write coil and update state."""
        await self.coordinator.async_write_coil(self._coil, value)

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data.get(self._coil.address)
        if data is not None:
            self._async_read_coil(data)
        self.async_write_ha_state()
