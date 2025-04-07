"""Support for covers."""

from __future__ import annotations

from typing import Any, cast

from aiocomelit import ComelitSerialBridgeObject
from aiocomelit.const import COVER, STATE_COVER, STATE_OFF, STATE_ON

from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ComelitConfigEntry, ComelitSerialBridge

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ComelitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comelit covers."""

    coordinator = cast(ComelitSerialBridge, config_entry.runtime_data)

    async_add_entities(
        ComelitCoverEntity(coordinator, device, config_entry.entry_id)
        for device in coordinator.data[COVER].values()
    )


class ComelitCoverEntity(
    CoordinatorEntity[ComelitSerialBridge], RestoreEntity, CoverEntity
):
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
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-{device.index}"
        self._attr_device_info = coordinator.platform_device_info(device, device.type)
        # Device doesn't provide a status so we assume UNKNOWN at first startup
        self._last_action: int | None = None
        self._last_state: str | None = None

    def _current_action(self, action: str) -> bool:
        """Return the current cover action."""
        is_moving = self.device_status == STATE_COVER.index(action)
        if is_moving:
            self._last_action = STATE_COVER.index(action)
        return is_moving

    @property
    def device_status(self) -> int:
        """Return current device status."""
        return self.coordinator.data[COVER][self._device.index].status

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""

        if self._last_state in [None, "unknown"]:
            return None

        if self.device_status != STATE_COVER.index("stopped"):
            return False

        if self._last_action:
            return self._last_action == STATE_COVER.index("closing")

        return self._last_state == CoverState.CLOSED

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return self._current_action("closing")

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return self._current_action("opening")

    async def _cover_set_state(self, action: int, state: int) -> None:
        """Set desired cover state."""
        self._last_state = self.state
        await self._api.set_device_status(COVER, self._device.index, action)
        self.coordinator.data[COVER][self._device.index].status = state
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._cover_set_state(STATE_OFF, 2)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        await self._cover_set_state(STATE_ON, 1)

    async def async_stop_cover(self, **_kwargs: Any) -> None:
        """Stop the cover."""
        if not self.is_closing and not self.is_opening:
            return

        action = STATE_ON if self.is_closing else STATE_OFF
        await self._cover_set_state(action, 0)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""

        await super().async_added_to_hass()

        if last_state := await self.async_get_last_state():
            self._last_state = last_state.state
