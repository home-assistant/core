"""Provide the functionality to group entities.

Legacy group support will not be extended for new domains.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.climate import HVACMode
from homeassistant.components.lock import LockState
from homeassistant.components.vacuum import VacuumActivity
from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
)
from homeassistant.const import (
    STATE_CLOSED,
    STATE_HOME,
    STATE_IDLE,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_OK,
    STATE_ON,
    STATE_OPEN,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_PROBLEM,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)

from .const import DOMAIN, REG_KEY

# EXCLUDED_DOMAINS and ON_OFF_STATES are considered immutable
# in respect that new platforms should not be added.
# The only maintenance allowed here is
# if existing platforms add new ON or OFF states.
EXCLUDED_DOMAINS: set[Platform | str] = {
    Platform.AIR_QUALITY,
    Platform.SENSOR,
    Platform.WEATHER,
}

ON_OFF_STATES: dict[Platform | str, tuple[set[str], str, str]] = {
    Platform.ALARM_CONTROL_PANEL: (
        {
            STATE_ON,
            AlarmControlPanelState.ARMED_AWAY,
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
            AlarmControlPanelState.ARMED_HOME,
            AlarmControlPanelState.ARMED_NIGHT,
            AlarmControlPanelState.ARMED_VACATION,
            AlarmControlPanelState.TRIGGERED,
        },
        STATE_ON,
        STATE_OFF,
    ),
    Platform.CLIMATE: (
        {
            STATE_ON,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.HEAT_COOL,
            HVACMode.AUTO,
            HVACMode.FAN_ONLY,
        },
        STATE_ON,
        STATE_OFF,
    ),
    Platform.COVER: ({STATE_OPEN}, STATE_OPEN, STATE_CLOSED),
    Platform.DEVICE_TRACKER: ({STATE_HOME}, STATE_HOME, STATE_NOT_HOME),
    Platform.LOCK: (
        {
            LockState.LOCKING,
            LockState.OPEN,
            LockState.OPENING,
            LockState.UNLOCKED,
            LockState.UNLOCKING,
        },
        LockState.UNLOCKED,
        LockState.LOCKED,
    ),
    Platform.MEDIA_PLAYER: (
        {
            STATE_ON,
            STATE_PAUSED,
            STATE_PLAYING,
            STATE_IDLE,
        },
        STATE_ON,
        STATE_OFF,
    ),
    "person": ({STATE_HOME}, STATE_HOME, STATE_NOT_HOME),
    "plant": ({STATE_PROBLEM}, STATE_PROBLEM, STATE_OK),
    Platform.VACUUM: (
        {
            STATE_ON,
            VacuumActivity.CLEANING,
            VacuumActivity.RETURNING,
            VacuumActivity.ERROR,
        },
        STATE_ON,
        STATE_OFF,
    ),
    Platform.WATER_HEATER: (
        {
            STATE_ON,
            STATE_ECO,
            STATE_ELECTRIC,
            STATE_PERFORMANCE,
            STATE_HIGH_DEMAND,
            STATE_HEAT_PUMP,
            STATE_GAS,
        },
        STATE_ON,
        STATE_OFF,
    ),
}


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the Group integration registry of integration platforms."""
    hass.data[REG_KEY] = GroupIntegrationRegistry(hass)

    await async_process_integration_platforms(
        hass, DOMAIN, _process_group_platform, wait_for_platforms=True
    )


class GroupProtocol(Protocol):
    """Define the format of group platforms."""

    def async_describe_on_off_states(
        self, hass: HomeAssistant, registry: GroupIntegrationRegistry
    ) -> None:
        """Describe group on off states."""


@callback
def _process_group_platform(
    hass: HomeAssistant, domain: str, platform: GroupProtocol
) -> None:
    """Process a group platform."""
    platform.async_describe_on_off_states(hass, hass.data[REG_KEY])


@dataclass(frozen=True, slots=True)
class SingleStateType:
    """Dataclass to store a single state type."""

    on_state: str
    off_state: str


class GroupIntegrationRegistry:
    """Class to hold a registry of integrations."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Imitialize registry."""
        self.hass = hass
        self.on_off_mapping: dict[str, str] = {STATE_ON: STATE_OFF}
        self.off_on_mapping: dict[str, str] = {STATE_OFF: STATE_ON}
        self.on_states_by_domain: dict[str, set[str]] = {}
        self.exclude_domains = EXCLUDED_DOMAINS.copy()
        self.state_group_mapping: dict[str, SingleStateType] = {}
        for domain, on_off_states in ON_OFF_STATES.items():
            self.on_off_states(domain, *on_off_states)

    @callback
    def exclude_domain(self, domain: str) -> None:
        """Exclude the current domain."""
        self.exclude_domains.add(domain)

    @callback
    def on_off_states(
        self,
        domain: Platform | str,
        on_states: set[str],
        default_on_state: str,
        off_state: str,
    ) -> None:
        """Register on and off states for the current domain.

        Legacy group support will not be extended for new domains.
        """
        for on_state in on_states:
            if on_state not in self.on_off_mapping:
                self.on_off_mapping[on_state] = off_state

        if off_state not in self.off_on_mapping:
            self.off_on_mapping[off_state] = default_on_state
        self.state_group_mapping[domain] = SingleStateType(default_on_state, off_state)

        self.on_states_by_domain[domain] = on_states
