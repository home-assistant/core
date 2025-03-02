"""Support for vacuum entities."""

from __future__ import annotations

from enum import StrEnum
import logging

from thinqconnect import DeviceType
from thinqconnect.integration import ExtendedProperty

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    StateVacuumEntityDescription,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
    "charging": VacuumActivity.DOCKED,
    "diagnosis": VacuumActivity.IDLE,
    "homing": VacuumActivity.RETURNING,
    "initializing": VacuumActivity.IDLE,
    "macrosector": VacuumActivity.IDLE,
    "monitoring_detecting": VacuumActivity.IDLE,
    "monitoring_moving": VacuumActivity.IDLE,
    "monitoring_positioning": VacuumActivity.IDLE,
    "pause": VacuumActivity.PAUSED,
    "reservation": VacuumActivity.IDLE,
    "setdate": VacuumActivity.IDLE,
    "sleep": VacuumActivity.IDLE,
    "standby": VacuumActivity.IDLE,
    "working": VacuumActivity.CLEANING,
    "error": VacuumActivity.ERROR,
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
    async_add_entities: AddConfigEntryEntitiesCallback,
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
        self._attr_activity = ROBOT_STATUS_TO_HA[self.data.current_state]

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
        elif self._attr_activity == VacuumActivity.PAUSED:
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
