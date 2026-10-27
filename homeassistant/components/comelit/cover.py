"""Support for covers."""

from datetime import datetime
from typing import Any, cast, override

from aiocomelit import ComelitDeviceObject
from aiocomelit.const import COVER, STATE_COVER, STATE_OFF, STATE_ON

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
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
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        coordinator: ComelitSerialBridge,
        device: ComelitDeviceObject,
        config_entry_entry_id: str,
    ) -> None:
        """Init cover entity."""
        super().__init__(coordinator, device, config_entry_entry_id)
        # Device doesn't report position, so it is estimated from travel time
        self._position: int | None = None
        self._movement_start: datetime | None = None
        self._movement_start_position = 0
        self._movement_target_position = 0
        self._position_timer: CALLBACK_TYPE | None = None

    def _current_action(self, action: str) -> bool:
        """Return the current cover action."""
        return self.device_status == STATE_COVER.index(action)

    @property
    def _travel_time(self) -> float:
        """Return the configured full travel time for this cover."""
        travel_times = self.coordinator.config_entry.options.get(CONF_TRAVEL_TIME, {})
        return cast(
            "float", travel_times.get(self.unique_id, DEFAULT_COVER_TRAVEL_TIME)
        )

    def _update_cover_position(self) -> None:
        """Update the estimated cover position attribute."""
        if self._movement_start is None:
            value = self._position
        else:
            elapsed = (dt_util.utcnow() - self._movement_start).total_seconds()
            distance = abs(
                self._movement_target_position - self._movement_start_position
            )
            traveled = min(distance, elapsed / self._travel_time * 100)
            direction = (
                1
                if self._movement_target_position >= self._movement_start_position
                else -1
            )
            value = round(self._movement_start_position + direction * traveled)
        self._attr_current_cover_position = value

    def _start_movement(self, target: int) -> None:
        """Record the start of a cover movement toward the given target."""
        self._cancel_position_timer()
        self._update_cover_position()
        start = self._attr_current_cover_position
        if start is None:
            start = 0 if target > 0 else 100
        self._movement_start_position = start
        self._movement_target_position = target
        self._movement_start = dt_util.utcnow()

    def _end_movement(self) -> None:
        """Freeze the estimated position at the end of a cover movement."""
        self._cancel_position_timer()
        self._update_cover_position()
        self._position = self._attr_current_cover_position
        self._movement_start = None

    def _is_moving_away_from_target(self) -> bool:
        """Return if the cover moves opposite to the tracked movement."""
        if self.is_opening:
            return self._movement_target_position < self._movement_start_position
        return self._movement_target_position > self._movement_start_position

    def _cancel_position_timer(self) -> None:
        """Cancel a pending scheduled stop, if any."""
        if self._position_timer is not None:
            self._position_timer()
            self._position_timer = None

    @property
    def device_status(self) -> int:
        """Return current device status."""
        return cast("int", self.coordinator.data[COVER][self._device.index].status)

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if (position := self.current_cover_position) is not None:
            return position <= 0

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

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        is_moving = self.is_opening or self.is_closing
        if is_moving and (
            self._movement_start is None or self._is_moving_away_from_target()
        ):
            # Movement started or reversed outside HA (wall switch, Comelit app)
            self._start_movement(100 if self.is_opening else 0)
        elif not is_moving and self._movement_start is not None:
            self._end_movement()
            if self._movement_target_position in (0, 100):
                # Stopped on its own during full travel: end stop reached
                self._position = self._movement_target_position
        self._update_cover_position()
        super()._handle_coordinator_update()

    async def _async_reach_target_position(self, _now: datetime) -> None:
        """Stop the cover once it reaches the requested position."""
        self._position_timer = None
        movement_start = self._movement_start
        # Status may be stale: stopping an idle cover would start it moving
        await self.coordinator.async_refresh()
        if (
            not self.coordinator.last_update_success
            # Superseded by a stop, a reversal or a newer command
            or self._movement_start is not movement_start
        ):
            return

        action = STATE_ON if self.is_closing else STATE_OFF
        await self._cover_set_state(action, 0)

    @bridge_api_call
    async def _cover_set_state(
        self, action: int, state: int, target: int | None = None
    ) -> None:
        """Set desired cover state, moving toward target or stopping if None."""
        await self.coordinator.api.set_device_status(COVER, self._device.index, action)
        if target is None:
            self._end_movement()
        else:
            self._start_movement(target)
        self.coordinator.data[COVER][self._device.index].status = state
        self._update_cover_position()
        self.async_write_ha_state()

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._cover_set_state(STATE_OFF, 2, 0)

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        await self._cover_set_state(STATE_ON, 1, 100)

    @override
    async def async_stop_cover(self, **_kwargs: Any) -> None:
        """Stop the cover."""
        if not self.is_closing and not self.is_opening:
            return

        action = STATE_ON if self.is_closing else STATE_OFF
        await self._cover_set_state(action, 0)

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        target = kwargs[ATTR_POSITION]

        # Let the motor end stop finish full travel instead of the timer
        if target == 0:
            await self.async_close_cover()
            return
        if target == 100:
            await self.async_open_cover()
            return

        self._update_cover_position()
        current = self._attr_current_cover_position
        if current is None:
            current = 0
        if target == current:
            await self.async_stop_cover()
            return

        if target > current:
            await self._cover_set_state(STATE_ON, 1, target)
        else:
            await self._cover_set_state(STATE_OFF, 2, target)

        duration = abs(target - current) / 100 * self._travel_time
        self._position_timer = async_call_later(
            self.hass, duration, self._async_reach_target_position
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""

        await super().async_added_to_hass()
        self.async_on_remove(self._cancel_position_timer)

        if (state := await self.async_get_last_state()) is not None:
            if (position := state.attributes.get(ATTR_CURRENT_POSITION)) is not None:
                self._position = position
            elif state.state == CoverState.CLOSED:
                self._position = 0
            elif state.state == CoverState.OPEN:
                self._position = 100

            self._update_cover_position()
