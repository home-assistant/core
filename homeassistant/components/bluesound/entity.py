"""Shared entity base for Bluesound integration."""

from pyblu import Player, SyncStatus

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_PORT, DOMAIN
from .coordinator import BluesoundCoordinator
from .utils import format_unique_id


class BluesoundEntity(CoordinatorEntity[BluesoundCoordinator]):
    """Common base class for Bluesound entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BluesoundCoordinator,
        player: Player,
        *,
        port: int,
        sync_status: SyncStatus,
        unique_id_prefix: str | None = None,
    ) -> None:
        """Initialize the Bluesound entity."""
        super().__init__(coordinator)
        self._player = player

        base_unique_id = format_unique_id(sync_status.mac, port)
        if unique_id_prefix is not None:
            self._attr_unique_id = f"{unique_id_prefix}-{base_unique_id}"
        else:
            self._attr_unique_id = base_unique_id

        if port == DEFAULT_PORT:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, format_mac(sync_status.mac))},
                connections={(CONNECTION_NETWORK_MAC, sync_status.mac)},
                name=sync_status.name,
                manufacturer=sync_status.brand,
                model=sync_status.model_name,
                model_id=sync_status.model,
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, format_unique_id(sync_status.mac, port))},
                name=sync_status.name,
                manufacturer=sync_status.brand,
                model=sync_status.model_name,
                model_id=sync_status.model,
            )
            # The leader may belong to a config entry that is not loaded yet.
            if leader_devices := dr.async_get(coordinator.hass).async_get_devices(
                identifiers={(DOMAIN, format_mac(sync_status.mac))}
            ):
                self._attr_device_info["via_device_id"] = leader_devices[0].id
