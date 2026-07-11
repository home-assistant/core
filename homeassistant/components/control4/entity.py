"""Base entity classes for the Control4 integration."""

import logging
from typing import Any, override

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_CONTROLLER_UNIQUE_ID, CONF_WEBSOCKET, DOMAIN

_LOGGER = logging.getLogger(__name__)


class Control4Entity(Entity):
    """Base entity for Control4 that receives state from WebSocket push events."""

    def __init__(
        self,
        entry_data: dict[str, Any],
        entry: ConfigEntry,
        name: str,
        idx: int,
        device_name: str | None,
        device_manufacturer: str | None,
        device_model: str | None,
        device_id: int,
        device_area: str | None,
        device_attributes: dict[str, Any],
    ) -> None:
        """Initialize a Control4 entity."""
        super().__init__()
        self.entry = entry
        self.entry_data = entry_data
        self._attr_has_entity_name = True
        self._attr_name = name
        self._attr_unique_id = str(idx)
        self._idx = idx
        self._controller_unique_id = entry_data[CONF_CONTROLLER_UNIQUE_ID]
        self._device_name = device_name
        self._device_manufacturer = device_manufacturer
        self._device_model = device_model
        self._device_id = device_id
        self._device_area = device_area
        self._extra_state_attributes: dict[str, Any] = device_attributes
        self._extra_state_attributes["item id"] = idx
        self._extra_state_attributes["parent item id"] = device_id
        self._attr_should_poll = False

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to WebSocket push events for this item."""
        await super().async_added_to_hass()
        websocket = self.entry_data[CONF_WEBSOCKET]

        def _register() -> None:
            websocket.add_item_callback(self._idx, self._update_callback)
            websocket.add_item_callback(self._device_id, self._update_callback)

        await self.hass.async_add_executor_job(_register)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe WebSocket callbacks."""
        try:
            self.entry_data[CONF_WEBSOCKET].remove_item_callback(
                self._idx, self._update_callback
            )
            self.entry_data[CONF_WEBSOCKET].remove_item_callback(
                self._device_id, self._update_callback
            )
        except KeyError:
            return

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
        """Merge push-event data into extra_state_attributes."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    for k, val in value.items():
                        self._extra_state_attributes[k] = val
                else:
                    self._extra_state_attributes[key] = value

    @override
    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return info of parent Control4 device."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            manufacturer=self._device_manufacturer,
            model=self._device_model,
            name=self._device_name,
            via_device=(DOMAIN, self._controller_unique_id),
            suggested_area=self._device_area,
        )

    @override
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return self._extra_state_attributes


class Control4CoordinatorEntity(CoordinatorEntity[Any]):
    """Coordinator-based entity for Control4 (used by media_player for position polling)."""

    def __init__(
        self,
        entry_data: dict[str, Any],
        coordinator: DataUpdateCoordinator[Any],
        name: str | None,
        idx: int,
        device_name: str | None,
        device_manufacturer: str | None,
        device_model: str | None,
        device_id: int,
        device_area: str | None,
        device_attributes: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entry_data = entry_data
        self._attr_name = name
        self._attr_unique_id = str(idx)
        self._idx = idx
        self._controller_unique_id = entry_data[CONF_CONTROLLER_UNIQUE_ID]
        self._device_name = device_name
        self._device_manufacturer = device_manufacturer
        self._device_model = device_model
        self._device_id = device_id
        self._device_area = device_area
        self._extra_state_attributes: dict[str, Any] = device_attributes
        self._extra_state_attributes["item id"] = idx
        self._extra_state_attributes["parent item id"] = device_id

    @override
    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return info of parent Control4 device."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            manufacturer=self._device_manufacturer,
            model=self._device_model,
            name=self._device_name,
            via_device=(DOMAIN, self._controller_unique_id),
            suggested_area=self._device_area,
        )

    @override
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        self._extra_state_attributes.update(self.coordinator.data.get(self._idx, {}))
        return self._extra_state_attributes
