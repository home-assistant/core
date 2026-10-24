"""Base entity classes for the Control4 integration."""

import logging
from typing import Any, ClassVar, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, Control4RuntimeData

_LOGGER = logging.getLogger(__name__)


class Control4Entity(Entity):
    """Base entity for Control4 that receives state from WebSocket push events."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    # Every subclass must declare the specific Control4 variable names its
    # properties read; anything else Control4 sends for the item is dropped.
    _ATTRIBUTES_OF_INTEREST: ClassVar[frozenset[str]]

    def __init__(
        self,
        entry_data: Control4RuntimeData,
        entry: ConfigEntry,
        name: str,
        idx: int,
        device_name: str | None,
        device_manufacturer: str | None,
        device_model: str | None,
        device_id: int,
        device_attributes: dict[str, Any],
    ) -> None:
        """Initialize a Control4 entity."""
        super().__init__()
        self.entry = entry
        self.entry_data = entry_data
        self._attr_name = name
        self._attr_unique_id = str(idx)
        self._idx = idx
        self._device_id = device_id
        self._device_name = device_name
        self._device_manufacturer = device_manufacturer
        self._device_model = device_model
        self._extra_state_attributes: dict[str, Any] = {
            key: value
            for key, value in device_attributes.items()
            if key in self._ATTRIBUTES_OF_INTEREST
        }

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return info of parent Control4 device of entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            manufacturer=self._device_manufacturer,
            model=self._device_model,
            name=self._device_name,
            via_device_id=dr.async_get_device_id_by_identifier(
                self.hass,
                (DOMAIN, self.entry_data.controller_unique_id),
                config_entry_id=self.entry.entry_id,
            ),
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to WebSocket push events for this item."""
        await super().async_added_to_hass()
        websocket = self.entry_data.websocket
        websocket.add_item_callback(self._idx, self._update_callback)
        websocket.add_item_callback(self._device_id, self._update_callback)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe WebSocket callbacks."""
        await super().async_will_remove_from_hass()
        websocket = self.entry_data.websocket
        websocket.remove_item_callback(self._idx, self._update_callback)
        websocket.remove_item_callback(self._device_id, self._update_callback)

    async def _update_callback(
        self, device: int, message: dict[str, Any] | bool
    ) -> None:
        """Handle a WebSocket push event."""
        if not isinstance(message, dict):
            if self._attr_available:
                _LOGGER.warning(
                    "Control4 entity %s (%s) is unavailable", self.name, self._idx
                )
            self._attr_available = False
        elif message.get("evtName") == "OnDataToUI":
            if not self._attr_available:
                _LOGGER.info(
                    "Control4 entity %s (%s) is available again", self.name, self._idx
                )
            self._attr_available = True
            await self._data_to_extra_state_attributes(message.get("data"))
        self.async_write_ha_state()

    async def _data_to_extra_state_attributes(self, data: Any) -> None:
        """Merge modeled keys from push-event data into extra_state_attributes."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    for k, val in value.items():
                        if k in self._ATTRIBUTES_OF_INTEREST:
                            self._extra_state_attributes[k] = (
                                None if val == "Undefined" else val
                            )
                elif key in self._ATTRIBUTES_OF_INTEREST:
                    self._extra_state_attributes[key] = (
                        None if value == "Undefined" else value
                    )


class Control4CoordinatorEntity(CoordinatorEntity[Any]):
    """Coordinator-based entity for Control4 (used by media_player for position polling)."""

    def __init__(
        self,
        entry_data: Control4RuntimeData,
        coordinator: DataUpdateCoordinator[Any],
        name: str | None,
        idx: int,
        device_name: str | None,
        device_manufacturer: str | None,
        device_model: str | None,
        device_id: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entry_data = entry_data
        self._attr_name = name
        self._attr_unique_id = str(idx)
        self._idx = idx
        self._device_id = device_id
        self._device_name = device_name
        self._device_manufacturer = device_manufacturer
        self._device_model = device_model

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return info of parent Control4 device of entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            manufacturer=self._device_manufacturer,
            model=self._device_model,
            name=self._device_name,
            via_device_id=dr.async_get_device_id_by_identifier(
                self.hass,
                (DOMAIN, self.entry_data.controller_unique_id),
                config_entry_id=self.coordinator.config_entry.entry_id,
            ),
        )
