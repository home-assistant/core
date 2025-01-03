"""DataUpdateCoordinator for the bryant_evolution module."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
import logging

from evolutionhttp import BryantEvolutionLocalClient

from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ZoneState:
    """Cached state of an Evolution zone."""

    curr_temp: int
    htsp: int
    clsp: int


@dataclass(frozen=True)
class _SystemState:
    """Cached state of a single Evolution system."""

    fan_mode: str
    hvac_mode: str
    is_hvac_active: bool
    zones: dict[int, _ZoneState]


@dataclass(frozen=True)
class EvolutionState:
    """Class to hold the cached state of all Evolution systems accessible through one SAM device."""

    systems: dict[int, _SystemState]

    def read_current_temperature(self, sys_id: int, zone_id: int) -> int:
        """Return the current temperature."""
        return self.systems[sys_id].zones[zone_id].curr_temp

    def read_fan_mode(self, sys_id: int) -> str:
        """Return the current fan mode."""
        return self.systems[sys_id].fan_mode

    def read_hvac_mode(self, sys_id: int) -> HVACMode:
        """Return the current HVAC mode."""
        evolution_mode = self.systems[sys_id].hvac_mode
        mode_enum = {
            "HEAT": HVACMode.HEAT,
            "COOL": HVACMode.COOL,
            "AUTO": HVACMode.HEAT_COOL,
            "OFF": HVACMode.OFF,
        }.get(evolution_mode.upper())
        if mode_enum is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_parse_hvac_mode",
                translation_placeholders={"mode": evolution_mode},
            )
        return mode_enum

    def read_target_temperatures(
        self, sys_id: int, zone_id: int
    ) -> tuple[int | None, int | None, int | None]:
        """Return the target temperatures.

        Specifically, returns a tuple with three integers. It will be either:
        1. (target-temp, None, None) if the mode is HEAT or COOL
        2. (None, heating-setpoint, cooling-setpoint) if the mode is HEAT_COOL.
        """
        mode = self.read_hvac_mode(sys_id)
        # Return target_temperature or target_temperature_{high, low} based on mode.
        match mode:
            case HVACMode.HEAT:
                return (self.systems[sys_id].zones[zone_id].htsp, None, None)
            case HVACMode.COOL:
                return (self.systems[sys_id].zones[zone_id].clsp, None, None)
            case HVACMode.HEAT_COOL:
                htsp = self.systems[sys_id].zones[zone_id].htsp
                clsp = self.systems[sys_id].zones[zone_id].clsp
                return (None, htsp, clsp)
            case HVACMode.OFF:
                return (None, None, None)
            case _:
                raise HomeAssistantError(f"Unknown HVAC mode {mode}")

    def read_hvac_action(self, sys_id: int, zone_id: int) -> HVACAction:
        """Return the HVAC action."""
        if not self.systems[sys_id].is_hvac_active:
            return HVACAction.OFF

        mode = self.read_hvac_mode(sys_id)
        match mode:
            case HVACMode.HEAT:
                return HVACAction.HEATING
            case HVACMode.COOL:
                return HVACAction.COOLING
            case HVACMode.OFF:
                return HVACAction.OFF
            case HVACMode.HEAT_COOL:
                (_, clsp, _) = self.read_target_temperatures(sys_id, zone_id)
                assert clsp is not None
                # In HEAT_COOL, we need to figure out what the actual action is
                # based on the setpoints.
                if self.read_current_temperature(sys_id, zone_id) > clsp:
                    # If the system is on and the current temperature is
                    # higher than the point at which heating would activate,
                    # then we must be cooling.
                    return HVACAction.COOLING
                return HVACAction.HEATING
        raise HomeAssistantError(f"Unknown mode: {mode}")


async def _read_evolution_state(
    system_to_zones: dict[int, list[int]], tty: str
) -> EvolutionState:
    """Read the state of the given systems and zones from the device at tty."""
    # Read each system's state.
    system_states: dict[int, _SystemState] = {}
    for sys_id, zone_ids in system_to_zones.items():
        system_states[sys_id] = await _read_system_state(sys_id, zone_ids, tty)
    return EvolutionState(systems=system_states)


async def _read_system_state(
    system_id: int, zone_ids: list[int], tty: str
) -> _SystemState:
    """Read the state of the given zones from the given system at tty."""
    # Create a client for an arbitrary (but known-valid) zone to read parameters
    # that are zone-independent.
    sys_client = await BryantEvolutionLocalClient.get_client(
        system_id, zone_ids[0], tty
    )
    fan_mode = (await sys_client.read_fan_mode()).lower()
    (hvac_mode, is_hvac_active) = await sys_client.read_hvac_mode()
    zones: dict[int, _ZoneState] = {}
    for zone_id in zone_ids:
        zones[zone_id] = await _read_zone_state(system_id, zone_id, tty)
    return _SystemState(
        fan_mode=fan_mode,
        hvac_mode=hvac_mode,
        is_hvac_active=is_hvac_active,
        zones=zones,
    )


async def _read_zone_state(system_id: int, zone_id: int, tty: str) -> _ZoneState:
    """Read the state of a given (system_id, zone_id) at tty."""
    client = await BryantEvolutionLocalClient.get_client(system_id, zone_id, tty)
    return _ZoneState(
        curr_temp=await client.read_current_temperature(),
        htsp=await client.read_heating_setpoint(),
        clsp=await client.read_cooling_setpoint(),
    )


class EvolutionCoordinator(DataUpdateCoordinator[EvolutionState]):
    """Class to manage fetching data from the Evolution API on a particular tty."""

    # Note: directly accessing the data member of this class is discouraged.
    # Prefer using the provided read_ functions, which are less error-prone.

    def __init__(
        self, hass: HomeAssistant, tty: str, system_zones: list[tuple[int, int]]
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"Bryant Evolution at {tty}",
            update_interval=timedelta(minutes=1),
            update_method=lambda: _read_evolution_state(
                self._system_to_zones, self.tty
            ),
            always_update=False,
        )
        self._system_to_zones: defaultdict[int, list[int]] = defaultdict(list)
        for system_id, zone_id in system_zones:
            self._system_to_zones[system_id].append(zone_id)
        self.tty = tty
