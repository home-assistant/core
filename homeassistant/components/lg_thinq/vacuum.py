"""Support for vacuum entities."""

from __future__ import annotations

from enum import StrEnum
import logging

from thinqconnect import DeviceType
from thinqconnect.integration import ExtendedProperty

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_RETURNING,
    StateVacuumEntity,
    StateVacuumEntityDescription,
    VacuumEntityFeature,
)
from homeassistant.const import STATE_IDLE, STATE_PAUSED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ThinqConfigEntry
from .entity import ThinQEntity

DEVICE_TYPE_VACUUM_MAP: dict[DeviceType, tuple[StateVacuumEntityDescription, ...]] = {
    DeviceType.ROBOT_CLEANER: (
        StateVacuumEntityDescription(
            key=ExtendedProperty.VACUUM,
            name=None,
        ),
    ),
}


class State(StrEnum):
    """State of device."""

    HOMING = "homing"
    PAUSE = "pause"
    RESUME = "resume"
    SLEEP = "sleep"
    START = "start"
    WAKE_UP = "wake_up"


ROBOT_STATUS_TO_HA = {
    "charging": STATE_DOCKED,
    "diagnosis": STATE_IDLE,
    "homing": STATE_RETURNING,
    "initializing": STATE_IDLE,
    "macrosector": STATE_IDLE,
    "monitoring_detecting": STATE_IDLE,
    "monitoring_moving": STATE_IDLE,
    "monitoring_positioning": STATE_IDLE,
    "pause": STATE_PAUSED,
    "reservation": STATE_IDLE,
    "setdate": STATE_IDLE,
    "sleep": STATE_IDLE,
    "standby": STATE_IDLE,
    "working": STATE_CLEANING,
    "error": STATE_ERROR,
}
ROBOT_BATT_TO_HA = {
    "moveless": 5,
    "dock_level": 5,
    "low": 30,
    "mid": 50,
    "high": 90,
    "full": 100,
    "over_charge": 100,
}
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an entry for vacuum platform."""
    entities: list[ThinQStateVacuumEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        if (
            descriptions := DEVICE_TYPE_VACUUM_MAP.get(
                coordinator.api.device.device_type
            )
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQStateVacuumEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(description.key)
                )

    if entities:
        async_add_entities(entities)


class ThinQStateVacuumEntity(ThinQEntity, StateVacuumEntity):
    """Represent a thinq vacuum platform."""

    _attr_supported_features = (
        VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.START
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
    )

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        # Update state.
        self._attr_state = ROBOT_STATUS_TO_HA[self.data.current_state]

        # Update battery.
        if (level := self.data.battery) is not None:
            self._attr_battery_level = (
                level if isinstance(level, int) else ROBOT_BATT_TO_HA.get(level, 0)
            )

        _LOGGER.debug(
            "[%s:%s] update status: %s -> %s (battery_level=%s)",
            self.coordinator.device_name,
            self.property_id,
            self.data.current_state,
            self.state,
            self.battery_level,
        )

    async def async_start(self, **kwargs) -> None:
        """Start the device."""
        if self.data.current_state == State.SLEEP:
            value = State.WAKE_UP
        elif self._attr_state == STATE_PAUSED:
            value = State.RESUME
        else:
            value = State.START

        _LOGGER.debug(
            "[%s:%s] async_start", self.coordinator.device_name, self.property_id
        )
        await self.async_call_api(
            self.coordinator.api.async_set_clean_operation_mode(self.property_id, value)
        )

    async def async_pause(self, **kwargs) -> None:
        """Pause the device."""
        _LOGGER.debug(
            "[%s:%s] async_pause", self.coordinator.device_name, self.property_id
        )
        await self.async_call_api(
            self.coordinator.api.async_set_clean_operation_mode(
                self.property_id, State.PAUSE
            )
        )

    async def async_return_to_base(self, **kwargs) -> None:
        """Return device to dock."""
        _LOGGER.debug(
            "[%s:%s] async_return_to_base",
            self.coordinator.device_name,
            self.property_id,
        )
        await self.async_call_api(
            self.coordinator.api.async_set_clean_operation_mode(
                self.property_id, State.HOMING
            )
        )
