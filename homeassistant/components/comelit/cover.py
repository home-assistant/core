"""Support for covers."""
from __future__ import annotations

from typing import Any

from aiocomelit import ComelitSerialBridgeObject
from aiocomelit.const import COVER, COVER_CLOSE, COVER_OPEN, COVER_STATUS

from homeassistant.components.cover import CoverDeviceClass, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ComelitSerialBridge


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comelit covers."""

    coordinator: ComelitSerialBridge = hass.data[DOMAIN][config_entry.entry_id]

    # Use config_entry.entry_id as base for unique_id because no serial number or mac is available
    async_add_entities(
        ComelitCoverEntity(coordinator, device, config_entry.entry_id)
        for device in coordinator.data[COVER].values()
    )


class ComelitCoverEntity(CoordinatorEntity[ComelitSerialBridge], CoverEntity):
    """Cover device."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: ComelitSerialBridge,
        device: ComelitSerialBridgeObject,
        config_entry_entry_id: str,
    ) -> None:
        """Init cover entity."""
        self._api = coordinator.api
        self._device = device
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry_entry_id}-{device.index}"
        self._attr_device_info = coordinator.platform_device_info(device, COVER)
        # Device doesn't provide a status so we assume CLOSE at startup
        self._last_action = COVER_STATUS.index("closing")

    def _current_action(self, action: str) -> bool:
        """Return the current cover action."""
        is_moving = self.device_status == COVER_STATUS.index(action)
        if is_moving:
            self._last_action = COVER_STATUS.index(action)
        return is_moving

    @property
    def device_status(self) -> int:
        """Return current device status."""
        return self.coordinator.data[COVER][self._device.index].status

    @property
    def is_closed(self) -> bool:
        """Return True if cover is closed."""
        if self.device_status != COVER_STATUS.index("stopped"):
            return False

        return bool(self._last_action == COVER_STATUS.index("closing"))

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return self._current_action("closing")

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return self._current_action("opening")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._api.cover_move(self._device.index, COVER_CLOSE)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        await self._api.cover_move(self._device.index, COVER_OPEN)

    async def async_stop_cover(self, **_kwargs: Any) -> None:
        """Stop the cover."""
        if not self.is_closing and not self.is_opening:
            return

        action = COVER_OPEN if self.is_closing else COVER_CLOSE
        await self._api.cover_move(self._device.index, action)
