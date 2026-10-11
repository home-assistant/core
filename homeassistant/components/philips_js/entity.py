"""Base Philips js entity."""

from typing import Any, override

from haphilipsjs.typing import (
    MenuItemsSettingsCurrentValueValue,
    MenuItemsSettingsNode,
    MenuItemsSettingsValueData,
)

from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PhilipsTVDataUpdateCoordinator

ATTR_NODE_ID = "node_id"
ATTR_CONTROLLABLE = "controllable"


class PhilipsJsEntity(CoordinatorEntity[PhilipsTVDataUpdateCoordinator]):
    """Base Philips js entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize light."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info


class PhilipsTVSettingsEntity(CoordinatorEntity[PhilipsTVDataUpdateCoordinator]):
    """A Philips TV menu settings entity."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _value: MenuItemsSettingsCurrentValueValue | None
    _data: MenuItemsSettingsValueData | None

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
        node: MenuItemsSettingsNode,
        name: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, node["node_id"])
        self._attr_unique_id = f"{coordinator.unique_id}_{node['node_id']}"
        self._attr_name = name
        self._node = node
        self._value = None
        self._data = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        if self._value:
            return self._value.get("Available", False)
        return False

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra metadata for the user."""
        controllable = self._value.get("Controllable") if self._value else None
        return {
            ATTR_NODE_ID: self._node["node_id"],
            ATTR_CONTROLLABLE: controllable,
        }

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._get_coordinator_data()

    def _get_coordinator_data(self) -> None:
        """Grab data from the coordinator."""
        self._value = self.coordinator.settings.get(self._node["node_id"])
        if self._value:
            self._data = self._value.get("data")

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._get_coordinator_data()
        self.async_write_ha_state()
