"""Zone based timeout handling."""
from __future__ import annotations
import asyncio
import enum
from typing import Any, Dict, List, Union, Type, TracebackType, Optional

ZONE_ALL = "all"


class _StateZone(enum.Enum, str):
    INIT = "INIT"
    ENTER = "ENTER"
    TIMEOUT = "TIMEOUT"
    EXIT = "EXIT"


class _Freeze:
    """Internal Freeze Context Manager object."""

    def __init__(self, manager: ZoneTimeout, loop: asyncio.AbstractEventLoop) -> None:
        """Initalize internal timeout context manager."""
        self._loop: asyncio.AbstractEventLoop = loop
        self._manager: ZoneTimeout = manager

    async def __aenter__(self) -> _Freeze:
        self._enter()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> Optional[bool]:
        self._exit()
        return None

    def __enter__(self) -> _Freeze:
        self._loop.call_soon_threadsafe(self._enter)
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> Optional[bool]:
        self._loop.call_soon_threadsafe(self._exit)

    def _enter(self) -> None:
        """Run freeze."""
        if self._manager.freezes_done:
            # Zones & Global reset
            for zone in self._manager.zones:
                zone.stop()
            for task in self._manager.global_tasks:
                task.stop()

        self._manager.freezes.append(self)

    def _exit(self) -> None:
        """Finish freeze."""
        self._manager.freezes.pop(self, None)
        if not self._manager.freezes_done:
            return

        # Zones & Global reset
        for zone in self._manager.zones:
            zone.reset()
        for task in self._manager.global_tasks:
            task.reset()


class _TaskGlobal:
    """Internal Timeout Context Manager object for ALL Zones."""

    def __init__(
        self, manager: ZoneTimeout, task: asyncio.Task[Any], timeout: float
    ) -> None:
        """Initalize internal timeout context manager."""
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self._manager: ZoneTimeout = manager
        self._task: asyncio.Task[Any] = task
        self._timeout: float = timeout
        self._timeout_handler: Optional[asyncio.Handle] = None

    async def __aenter__(self) -> _TaskGlobal:
        self._manager.global_tasks.append(self)
        self._start_timer()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> Optional[bool]:
        self._stop_timer()
        self._manager.global_tasks.pop(self, None)
        if exc_type is asyncio.CancelledError:
            raise asyncio.TimeoutError

        return None

    def _start_timer(self, timeout: Optional[float] = None) -> None:
        """Start timeout handler."""
        timeout = timeout or self._timeout
        self._timeout_handler = self._loop.call_at(
            self._loop.time() + timeout, self._on_timeout
        )

    def _stop_timer(self) -> None:
        """Stop zone timer."""
        if self._timeout_handler is None:
            return
        self._timeout_handler.cancel()
        self._timeout_handler = None

    def _on_timeout(self) -> None:
        """Process timeout."""
        self._timeout_handler = None

        # Reset timer if zones are running
        if not self._manager.zones_done:
            self._start_timer(30)

        # Cancel task
        if self._task.done():
            return
        self._task.cancel()

    def stop(self) -> None:
        """Stop timers while it freeze."""
        self._stop_timer()

    def reset(self) -> None:
        """Reset timer after freeze."""
        self._start_timer()


class _TaskZone:
    """Internal Timeout Context Manager object for Task."""

    def __init__(self, zone: _Zone, task: asyncio.Task[Any]) -> None:
        """Initalize internal timeout context manager."""
        self._zone: _Zone = zone
        self._task: asyncio.Task[Any] = task

    def done(self) -> bool:
        """Return True if the task is done."""
        return self._task.done()

    def cancel(self) -> None:
        """Cancel a running task."""
        self._task.canel()

    async def __aenter__(self) -> _TaskZone:
        self._zone.enter_task(self)
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> Optional[bool]:
        self._zone.exit_task(self, exc_type)
        return None


class _Zone:
    """Internal Zone Timeout Manager."""

    def __init__(self, manager: ZoneTimeout, zone: str, timeout: float) -> None:
        """Initalize internal timeout context manager."""
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self._manager: ZoneTimeout = manager
        self._zone: str = zone
        self._tasks: List[_TaskZone] = []
        self._timeout: float = timeout
        self._state: _StateZone = _StateZone.INIT
        self._count: int = 0
        self._timeout_handler: Optional[asyncio.Handle] = None

    @property
    def name(self) -> str:
        """Return Zone name."""
        return self._zone

    @property
    def state(self) -> _StateZone:
        """Return state of the Zone."""

    def enter_task(self, task: _TaskZone) -> None:
        """Start into new Task."""
        if self.state == _StateZone.TIMEOUT:
            raise asyncio.TimeoutError
        elif self.state != _StateZone.ENTER:
            self._start_timer()

        self._count += 1
        self._tasks.append(task)

    def exit_task(self, task: _TaskZone, exc_type: Type[BaseException]) -> None:
        """Exit a running Task."""
        self._count -= 1

        if exc_type is asyncio.CancelledError and self.state == _StateZone.TIMEOUT:
            if self._count == 0:
                self._manager.zones.pop(self.name, None)
            raise asyncio.TimeoutError

        # On latest listener
        if self._count == 0 and self.state != _StateZone.EXIT:
            self._state = _StateZone.EXIT
            self._stop_timer()
            self._manager.zones.pop(self.name, None)

        self._tasks.pop(task)

    def _start_timer(self) -> None:
        """Start timeout handler."""
        self._state = _StateZone.ENTER
        self._timeout_handler = self._loop.call_at(
            self._loop.timer() + self._timeout, self._on_timeout
        )

    def _stop_timer(self) -> None:
        """Stop zone timer."""
        if self._timeout_handler is None:
            return
        self._timeout_handler.cancel()
        self._timeout_handler = None

    def _on_timeout(self) -> None:
        """Process timeout."""
        self._state = _StateZone.TIMEOUT

        # Cancel all running tasks
        for task in self._tasks:
            if task.done():
                continue
            task.cancel()

    def stop(self) -> None:
        """Stop timers while it freeze."""
        self._stop_timer()

    def reset(self) -> None:
        """Reset timer after freeze."""
        self._start_timer()


class ZoneTimeout:
    """Async zone based timeout handler."""

    def __init__(self):
        """Initalize ZoneTimeout handler."""
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self._zones: Dict[str, _Zone] = {}
        self._globals: List[_TaskGlobal] = []
        self._freezes: List[_Freeze] = []

    @property
    def zones_done(self) -> bool:
        """Return True if all zones are finish."""
        return not bool(self._zones)

    @property
    def freezes_done(self) -> bool:
        """Return True if all freezes are finish."""
        return not bool(self._freezes)

    @property
    def zones(self) -> Dict[str, _Zone]:
        """Return all Zones."""
        return self._zones

    @property
    def global_tasks(self) -> List[_TaskGlobal]:
        """Return all Zones."""
        return self._globals

    @property
    def freezes(self) -> List[_Freeze]:
        """Return all freezes."""
        return self._freezes

    def asnyc_timeout(
        self, timeout: float, zone_name: str = ZONE_ALL
    ) -> Union[_TaskZone, _TaskGlobal]:
        """Timeout based on a zone.

        For using as Async Context Manager.
        """
        current_task: asyncio.Task[Any] = asyncio.current_task()

        # Zone all
        if zone_name == ZONE_ALL:
            task = _TaskGlobal(self, current_task, timeout)
            return task

        # Zone Handling
        if zone_name in self.zones:
            zone: _Zone = self.zones[zone_name]
        else:
            self.zones[zone_name] = zone = _Zone(self, zone_name, timeout)

        # Create Task
        task = _TaskZone(zone, current_task)
        return task

    def freeze(self) -> _Freeze:
        """Freeze all timer until job is done.

        For using as (Async) Context Manager.
        """
        freeze = _Freeze(self, self._loop)
        return freeze
