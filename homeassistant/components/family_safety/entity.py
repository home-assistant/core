"""Base entity definition for Family Safety."""

from __future__ import annotations

from pyfamilysafety import Account

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FamilySafetyCoordinator


class FamilySafetyDevice(CoordinatorEntity[FamilySafetyCoordinator]):
    """Base entity definition for Family Safety."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: FamilySafetyCoordinator, account: Account, key: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.account = account
        self._attr_unique_id = f"{account.user_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account.user_id)},
            manufacturer="Microsoft",
            name=f"{account.first_name} {account.surname}",
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.account.add_account_callback(self.async_write_ha_state)

    async def async_removed_from_registry(self) -> None:
        """When entity is removed from hass."""
        await super().async_removed_from_registry()
        self.account.remove_account_callback(self.async_write_ha_state)
