"""Base Philips js entity."""

from typing import Any, override

from haphilipsjs.typing import (
    MenuItemsSettingsCurrentValueValue,
    MenuItemsSettingsNode,
    MenuItemsSettingsUpdateValueData,
    MenuItemsSettingsValueData,
)

from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_CONTROLLABLE, ATTR_NODE_ID
from .coordinator import PhilipsTVDataUpdateCoordinator


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


class PhilipsTVSettingsEntity(PhilipsJsEntity):
    """Base entity for a Philips TV menu setting."""

    _attr_unique_id: str
    _value: MenuItemsSettingsCurrentValueValue | None
    _data: MenuItemsSettingsValueData | None

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
        node: MenuItemsSettingsNode,
        name: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id}_menu_{node['node_id']}"
        self._attr_name = name
        self._attr_entity_category = EntityCategory.CONFIG
        self._node = node
        self._value = None
        self._data = None

    @override
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Settings are kept from the last update while the TV is off
        if not super().available or not self.coordinator.api.on:
            return False

        if self._value:
            return self._value.get("Available", False)
        return False

    @override
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra metadata for user."""
        if self._value:
            controllable = self._value.get("Controllable")
        else:
            controllable = None

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
        """Grab data from coordinator."""
        self._value = self.coordinator.settings.get(self._node["node_id"])
        self._data = self._value.get("data") if self._value else None

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._get_coordinator_data()
        self.async_write_ha_state()

    async def _async_update_value(self, data: MenuItemsSettingsUpdateValueData) -> None:
        """Send a new value for this node to the TV."""
        await self.coordinator.async_update_menu_setting(self._node["node_id"], data)
