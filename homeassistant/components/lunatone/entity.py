"""Base entity for Lunatone."""

from typing import Any, TypeVar, override

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .coordinator import LunatoneInfoDataUpdateCoordinator
from .helpers import format_device_identifier

T = TypeVar("T", bound=DataUpdateCoordinator[Any])


class LunatoneEntity(CoordinatorEntity[T]):
    """Representation of a Lunatone entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: T,
        coordinator_info: LunatoneInfoDataUpdateCoordinator,
        line_id: int | None = None,
    ) -> None:
        """Initialize a Lunatone entity."""
        super().__init__(coordinator)
        self.coordinator_info = coordinator_info
        self.line_id = line_id

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        if self.line_id is not None:
            self.async_on_remove(
                self.coordinator_info.async_add_listener(self._handle_info_update)
            )

    @callback
    def _handle_info_update(self) -> None:
        assert self.line_id is not None

        config_entry = self.coordinator.config_entry
        assert config_entry is not None
        assert config_entry.unique_id is not None

        config_entry_id = config_entry.entry_id
        device_registry = dr.async_get(self.hass)
        linked_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, format_device_identifier(config_entry.unique_id, self.line_id)),
            config_entry_id,
        )

        if (
            linked_device
            and self.registry_entry
            and self.registry_entry.device_id is not None
            and self.registry_entry.device_id != linked_device.id
        ):
            device = device_registry.async_get(
                self.registry_entry.device_id, include_child_devices=False
            )
            if device and device.via_device_id != linked_device.id:
                device_registry.async_update_device(
                    device.id, via_device_id=linked_device.id
                )

        self.async_write_ha_state()
