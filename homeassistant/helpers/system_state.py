"""Helpers to track pending restarts of the running Home Assistant instance.

The flags tracked here latch: once set, nothing clears them. Restarting
Home Assistant creates a fresh instance, and that is what clears them.

An admin can put off a pending restart. That only hides it from the
interface until another integration asks; the restart stays required.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.signal_type import SignalType

from .dispatcher import async_dispatcher_connect, async_dispatcher_send_internal

DATA_SYSTEM_STATE: HassKey[SystemState] = HassKey("system_state")
SIGNAL_SYSTEM_STATE_UPDATED: SignalType[SystemState] = SignalType(
    "system_state_updated"
)


@dataclass(slots=True, frozen=True)
class SystemState:
    """Snapshot of the pending restart state of the running instance."""

    home_assistant_restart_sources: frozenset[str] = frozenset()
    home_assistant_restart_dismissed_sources: frozenset[str] = frozenset()

    @property
    def home_assistant_restart_required(self) -> bool:
        """Return if a restart of Home Assistant is required."""
        return bool(self.home_assistant_restart_sources)

    @property
    def home_assistant_restart_dismissed(self) -> bool:
        """Return if the pending restart was put off by an admin."""
        return self.home_assistant_restart_required and (
            self.home_assistant_restart_sources
            <= self.home_assistant_restart_dismissed_sources
        )

    def as_dict(self) -> dict[str, bool | list[str]]:
        """Return a JSON serializable representation."""
        return {
            "home_assistant_restart_dismissed": self.home_assistant_restart_dismissed,
            "home_assistant_restart_required": self.home_assistant_restart_required,
            "home_assistant_restart_sources": sorted(
                self.home_assistant_restart_sources
            ),
        }


@callback
def async_get(hass: HomeAssistant) -> SystemState:
    """Return the system state of the running instance."""
    return hass.data.get(DATA_SYSTEM_STATE) or SystemState()


@callback
def _async_update(hass: HomeAssistant, system_state: SystemState) -> None:
    """Store a new snapshot and tell the subscribers."""
    hass.data[DATA_SYSTEM_STATE] = system_state
    async_dispatcher_send_internal(hass, SIGNAL_SYSTEM_STATE_UPDATED, system_state)


@callback
def async_set_home_assistant_restart_required(hass: HomeAssistant, domain: str) -> None:
    """Flag that Home Assistant needs a restart to apply a change.

    The domain is the integration that asks for the restart. It is listed
    to the user, so they can see what is waiting for the restart.
    """
    hass.verify_event_loop_thread(
        "system_state.async_set_home_assistant_restart_required"
    )

    system_state = async_get(hass)
    if domain in system_state.home_assistant_restart_sources:
        return

    _async_update(
        hass,
        replace(
            system_state,
            home_assistant_restart_sources=(
                system_state.home_assistant_restart_sources | {domain}
            ),
        ),
    )


@callback
def async_subscribe(
    hass: HomeAssistant, listener: Callable[[SystemState], None]
) -> CALLBACK_TYPE:
    """Subscribe to changes of the system state."""
    return async_dispatcher_connect(hass, SIGNAL_SYSTEM_STATE_UPDATED, listener)


@callback
def async_dismiss(hass: HomeAssistant) -> None:
    """Put off what is pending right now, until something new asks."""
    hass.verify_event_loop_thread("system_state.async_dismiss")

    system_state = async_get(hass)
    dismissed = replace(
        system_state,
        home_assistant_restart_dismissed_sources=(
            system_state.home_assistant_restart_sources
        ),
    )
    if dismissed == system_state:
        return

    _async_update(hass, dismissed)
