"""Support for covers."""

from datetime import datetime
from typing import Any, cast, override

from aiocomelit import ComelitSerialBridgeObject
from aiocomelit.const import COVER, STATE_COVER, STATE_OFF, STATE_ON

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import CONF_TRAVEL_TIME, DEFAULT_COVER_TRAVEL_TIME, ObjectClassType
from .coordinator import ComelitConfigEntry, ComelitSerialBridge
from .entity import ComelitBridgeBaseEntity
from .utils import bridge_api_call, new_device_listener

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ComelitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comelit covers."""

    coordinator = cast(ComelitSerialBridge, config_entry.runtime_data)

    def _add_new_entities(new_devices: list[ObjectClassType], dev_type: str) -> None:
        """Add entities for new monitors."""
        entities = [
            ComelitCoverEntity(coordinator, device, config_entry.entry_id)
            for device in coordinator.data[dev_type].values()
            if device in new_devices
        ]
        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        new_device_listener(coordinator, _add_new_entities, COVER)
    )


class ComelitCoverEntity(ComelitBridgeBaseEntity, RestoreEntity, CoverEntity):
    """Cover device."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_name = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(
        self,
        coordinator: ComelitSerialBridge,
        device: ComelitSerialBridgeObject,
        config_entry_entry_id: str,
    ) -> None:
        """Init cover entity."""
        super().__init__(coordinator, device, config_entry_entry_id)
        # Device doesn't provide a status so we assume UNKNOWN at first startup
        self._last_action: int | None = None
        # Device doesn't report position, so it is estimated from travel time
        self._position: int | None = None
        self._movement_start: datetime | None = None

    def _current_action(self, action: str) -> bool:
        """Return the current cover action."""
        is_moving = self.device_status == STATE_COVER.index(action)
        if is_moving:
            self._last_action = STATE_COVER.index(action)
        return is_moving

    @property
    def _travel_time(self) -> int:
        """Return the configured full travel time for this cover."""
        travel_times = self.coordinator.config_entry.options.get(CONF_TRAVEL_TIME, {})
        return cast("int", travel_times.get(self.entity_id, DEFAULT_COVER_TRAVEL_TIME))

    def _estimate_position(self) -> int | None:
        """Return the current estimated cover position."""
        if self._movement_start is None:
            return self._position

        elapsed = (dt_util.utcnow() - self._movement_start).total_seconds()
        progress = min(100, round(elapsed / self._travel_time * 100))

        return progress if self.is_opening else 100 - progress

    @property
    def device_status(self) -> int:
        """Return current device status."""
        return cast("int", self.coordinator.data[COVER][self._device.index].status)

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""

        if self._last_action:
            return self._last_action == STATE_COVER.index("closing")

        return None

    @property
    @override
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return bool(self._current_action("closing"))

    @property
    @override
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return self._current_action("opening")

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        return self._estimate_position()

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self._movement_start is not None
            and not self.is_opening
            and not self.is_closing
        ):
            self._position = (
                100 if self._last_action == STATE_COVER.index("opening") else 0
            )
            self._movement_start = None
        super()._handle_coordinator_update()

    @bridge_api_call
    async def _cover_set_state(self, action: int, state: int) -> None:
        """Set desired cover state."""
        await self.coordinator.api.set_device_status(COVER, self._device.index, action)
        self.coordinator.data[COVER][self._device.index].status = state
        self.async_write_ha_state()

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self._movement_start = dt_util.utcnow()
        await self._cover_set_state(STATE_OFF, 2)

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        self._movement_start = dt_util.utcnow()
        await self._cover_set_state(STATE_ON, 1)

    @override
    async def async_stop_cover(self, **_kwargs: Any) -> None:
        """Stop the cover."""
        if not self.is_closing and not self.is_opening:
            return

        action = STATE_ON if self.is_closing else STATE_OFF
        self._position = 0 if self.is_closing else 100
        self._movement_start = None
        await self._cover_set_state(action, 0)

    @override
    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""

        await super().async_added_to_hass()

        if (state := await self.async_get_last_state()) is not None:
            if state.state == CoverState.CLOSED:
                self._last_action = STATE_COVER.index(CoverState.CLOSING)
                self._position = 0
            if state.state == CoverState.OPEN:
                self._last_action = STATE_COVER.index(CoverState.OPENING)
                self._position = 100

            self._attr_is_closed = state.state == CoverState.CLOSED
