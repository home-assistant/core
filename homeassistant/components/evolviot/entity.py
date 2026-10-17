"""Base entities for EvolvIOT."""

from typing import override

from pyevolviot import (
    EvolvIOTApiError,
    EvolvIOTEntity as EvolvIOTEntityModel,
    EvolvIOTState,
)

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EvolvIOTDataUpdateCoordinator


class EvolvIOTEntity(CoordinatorEntity[EvolvIOTDataUpdateCoordinator]):
    """Base EvolvIOT entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EvolvIOTDataUpdateCoordinator,
        entity: EvolvIOTEntityModel,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        config_entry = coordinator.config_entry
        assert config_entry is not None
        entry_unique_id = config_entry.unique_id
        assert entry_unique_id is not None
        self._backend_entity_id = entity.entity_id
        self._fallback_entity = entity
        self._attr_unique_id = f"{entry_unique_id}/{entity.unique_id}"
        self._attr_name = entity.name

        device = entity.device
        device_id = device.id or entity.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_unique_id}/{device_id}")},
            name=device.name or "EvolvIOT Device",
            manufacturer=device.manufacturer or "EvolvIOT",
            model=device.model or None,
        )

    @property
    def backend_entity(self) -> EvolvIOTEntityModel:
        """Return latest backend entity metadata."""
        return self.coordinator.entities.get(
            self._backend_entity_id, self._fallback_entity
        )

    @property
    def backend_state(self) -> EvolvIOTState | None:
        """Return latest backend state."""
        return self.coordinator.states.get(self._backend_entity_id)

    @property
    @override
    def available(self) -> bool:
        """Return availability from EvolvIOT."""
        state = self.backend_state
        return super().available and bool(state and state.available)

    async def _async_send_command(self, command: str) -> None:
        """Send a command to EvolvIOT."""
        try:
            await self.coordinator.async_command(self._backend_entity_id, command)
        except EvolvIOTApiError as err:
            raise HomeAssistantError("Failed to send EvolvIOT command") from err
