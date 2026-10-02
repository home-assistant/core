"""Helpers to track pending restarts of the running Home Assistant instance.

The flags tracked here latch: once set, nothing clears them. Restarting
Home Assistant creates a fresh instance, and that is what clears them.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.signal_type import SignalType

from .dispatcher import async_dispatcher_connect, async_dispatcher_send_internal

DATA_SYSTEM_STATE: HassKey[SystemState] = HassKey("system_state")
SIGNAL_SYSTEM_STATE_UPDATED: SignalType[SystemState] = SignalType(
    "system_state_updated"
)


@dataclass(slots=True)
class SystemState:
    """Pending restart state of the running Home Assistant instance."""

    home_assistant_restart_sources: set[str] = field(default_factory=set)

    @property
    def home_assistant_restart_required(self) -> bool:
        """Return if a restart of Home Assistant is required."""
        return bool(self.home_assistant_restart_sources)

    def as_dict(self) -> dict[str, bool | list[str]]:
        """Return a JSON serializable representation."""
        return {
            "home_assistant_restart_required": self.home_assistant_restart_required,
            "home_assistant_restart_sources": sorted(
                self.home_assistant_restart_sources
            ),
        }


@callback
def async_get(hass: HomeAssistant) -> SystemState:
    """Return the system state of the running instance."""
    if (system_state := hass.data.get(DATA_SYSTEM_STATE)) is None:
        system_state = hass.data[DATA_SYSTEM_STATE] = SystemState()

    return system_state


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

    system_state.home_assistant_restart_sources.add(domain)
    async_dispatcher_send_internal(hass, SIGNAL_SYSTEM_STATE_UPDATED, system_state)


@callback
def async_subscribe(
    hass: HomeAssistant, listener: Callable[[SystemState], None]
) -> CALLBACK_TYPE:
    """Subscribe to changes of the system state.

    The listener must be a callback: it gets the live state, which a listener
    running in the executor would only read after it changed again.
    """
    return async_dispatcher_connect(hass, SIGNAL_SYSTEM_STATE_UPDATED, listener)
