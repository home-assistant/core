"""Helpers for Home Assistant dispatcher & internal component/platform."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from functools import partial
import logging
from typing import Any, Generic, TypeVarTuple, overload

from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.logging import catch_log_exception

_Ts = TypeVarTuple("_Ts")

_LOGGER = logging.getLogger(__name__)
DATA_DISPATCHER = "dispatcher"


@dataclass(frozen=True)
class SignalType(Generic[*_Ts]):
    """Generic string class for signal to improve typing."""

    name: str

    def __hash__(self) -> int:
        """Return hash of name."""

        return hash(self.name)

    def __eq__(self, other: Any) -> bool:
        """Check equality for dict keys to be compatible with str."""

        if isinstance(other, str):
            return self.name == other
        if isinstance(other, SignalType):
            return self.name == other.name
        return False


_DispatcherDataType = dict[
    SignalType[*_Ts] | str,
    dict[
        Callable[[*_Ts], Any] | Callable[..., Any],
        HassJob[..., None | Coroutine[Any, Any, None]] | None,
    ],
]


@overload
@bind_hass
def dispatcher_connect(
    hass: HomeAssistant, signal: SignalType[*_Ts], target: Callable[[*_Ts], None]
) -> Callable[[], None]:
    ...


@overload
@bind_hass
def dispatcher_connect(
    hass: HomeAssistant, signal: str, target: Callable[..., None]
) -> Callable[[], None]:
    ...


@bind_hass  # type: ignore[misc]  # workaround; exclude typing of 2 overload in func def
def dispatcher_connect(
    hass: HomeAssistant,
    signal: SignalType[*_Ts],
    target: Callable[[*_Ts], None],
) -> Callable[[], None]:
    """Connect a callable function to a signal."""
    async_unsub = run_callback_threadsafe(
        hass.loop, async_dispatcher_connect, hass, signal, target
    ).result()

    def remove_dispatcher() -> None:
        """Remove signal listener."""
        run_callback_threadsafe(hass.loop, async_unsub).result()

    return remove_dispatcher


@callback
def _async_remove_dispatcher(
    dispatchers: _DispatcherDataType[*_Ts],
    signal: SignalType[*_Ts] | str,
    target: Callable[[*_Ts], Any] | Callable[..., Any],
) -> None:
    """Remove signal listener."""
    try:
        signal_dispatchers = dispatchers[signal]
        del signal_dispatchers[target]
        # Cleanup the signal dict if it is now empty
        # to prevent memory leaks
        if not signal_dispatchers:
            del dispatchers[signal]
    except (KeyError, ValueError):
        # KeyError is key target listener did not exist
        # ValueError if listener did not exist within signal
        _LOGGER.warning("Unable to remove unknown dispatcher %s", target)


@overload
@callback
@bind_hass
def async_dispatcher_connect(
    hass: HomeAssistant, signal: SignalType[*_Ts], target: Callable[[*_Ts], Any]
) -> Callable[[], None]:
    ...


@overload
@callback
@bind_hass
def async_dispatcher_connect(
    hass: HomeAssistant, signal: str, target: Callable[..., Any]
) -> Callable[[], None]:
    ...


@callback
@bind_hass
def async_dispatcher_connect(
    hass: HomeAssistant,
    signal: SignalType[*_Ts] | str,
    target: Callable[[*_Ts], Any] | Callable[..., Any],
) -> Callable[[], None]:
    """Connect a callable function to a signal.

    This method must be run in the event loop.
    """
    if DATA_DISPATCHER not in hass.data:
        hass.data[DATA_DISPATCHER] = {}

    dispatchers: _DispatcherDataType[*_Ts] = hass.data[DATA_DISPATCHER]

    if signal not in dispatchers:
        dispatchers[signal] = {}

    dispatchers[signal][target] = None
    # Use a partial for the remove since it uses
    # less memory than a full closure since a partial copies
    # the body of the function and we don't have to store
    # many different copies of the same function
    return partial(_async_remove_dispatcher, dispatchers, signal, target)


@overload
@bind_hass
def dispatcher_send(hass: HomeAssistant, signal: SignalType[*_Ts], *args: *_Ts) -> None:
    ...


@overload
@bind_hass
def dispatcher_send(hass: HomeAssistant, signal: str, *args: Any) -> None:
    ...


@bind_hass  # type: ignore[misc]  # workaround; exclude typing of 2 overload in func def
def dispatcher_send(hass: HomeAssistant, signal: SignalType[*_Ts], *args: *_Ts) -> None:
    """Send signal and data."""
    hass.loop.call_soon_threadsafe(async_dispatcher_send, hass, signal, *args)


def _format_err(
    signal: SignalType[*_Ts] | str,
    target: Callable[[*_Ts], Any] | Callable[..., Any],
    *args: Any,
) -> str:
    """Format error message."""
    return "Exception in {} when dispatching '{}': {}".format(
        # Functions wrapped in partial do not have a __name__
        getattr(target, "__name__", None) or str(target),
        signal,
        args,
    )


def _generate_job(
    signal: SignalType[*_Ts] | str, target: Callable[[*_Ts], Any] | Callable[..., Any]
) -> HassJob[..., None | Coroutine[Any, Any, None]]:
    """Generate a HassJob for a signal and target."""
    return HassJob(
        catch_log_exception(target, partial(_format_err, signal, target)),
        f"dispatcher {signal}",
    )


@overload
@callback
@bind_hass
def async_dispatcher_send(
    hass: HomeAssistant, signal: SignalType[*_Ts], *args: *_Ts
) -> None:
    ...


@overload
@callback
@bind_hass
def async_dispatcher_send(hass: HomeAssistant, signal: str, *args: Any) -> None:
    ...


@callback
@bind_hass
def async_dispatcher_send(
    hass: HomeAssistant, signal: SignalType[*_Ts] | str, *args: *_Ts
) -> None:
    """Send signal and data.

    This method must be run in the event loop.
    """
    if (maybe_dispatchers := hass.data.get(DATA_DISPATCHER)) is None:
        return
    dispatchers: _DispatcherDataType[*_Ts] = maybe_dispatchers
    if (target_list := dispatchers.get(signal)) is None:
        return

    for target, job in list(target_list.items()):
        if job is None:
            job = _generate_job(signal, target)
            target_list[target] = job
        hass.async_run_hass_job(job, *args)
