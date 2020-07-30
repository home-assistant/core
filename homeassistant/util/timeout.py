"""Zone based timeout handling."""
from __future__ import annotations
import asyncio
import enum
from typing import Any, Dict, List, Union, Type, Optional
from types import TracebackType

ZONE_GLOBAL = "global"


class _State(str, enum.Enum):
    """States of a Zone."""

    INIT = "INIT"
    ENTER = "ENTER"
    TIMEOUT = "TIMEOUT"
    EXIT = "EXIT"
    FREEZE = "FREEZE"


class _FreezeGlobal:
    """Internal Freeze Context Manager object for Global."""

    def __init__(self, manager: ZoneTimeout, loop: asyncio.AbstractEventLoop) -> None:
        """Initalize internal timeout context manager."""
        self._loop: asyncio.AbstractEventLoop = loop
        self._manager: ZoneTimeout = manager

    async def __aenter__(self) -> _FreezeGlobal:
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

    def __enter__(self) -> _FreezeGlobal:
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
        if not self._manager.freezes_done:
            return

        # Global reset
        for task in self._manager.global_tasks:
            task.pause()

        # Zones reset
        for zone in self._manager.zones.values():
            if not zone.freezes_done:
                continue
            zone.pause()

        self._manager.global_freezes.append(self)

    def _exit(self) -> None:
        """Finish freeze."""
        self._manager.global_freezes.remove(self)
        if not self._manager.freezes_done:
            return

        # Global reset
        for task in self._manager.global_tasks:
            task.reset()

        # Zones reset
        for zone in self._manager.zones.values():
            if not zone.freezes_done:
                continue
            zone.reset()


class _FreezeZone:
    """Internal Freeze Context Manager object for Zone."""

    def __init__(self, zone: _Zone, loop: asyncio.AbstractEventLoop) -> None:
        """Initalize internal timeout context manager."""
        self._loop: asyncio.AbstractEventLoop = loop
        self._zone: _Zone = zone

    async def __aenter__(self) -> _FreezeZone:
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

    def __enter__(self) -> _FreezeZone:
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
        if self._zone.freezes_done:
            self._zone.pause()
        self._zone.freezes.append(self)

    def _exit(self) -> None:
        """Finish freeze."""
        self._zone.freezes.remove(self)
        if not self._zone.freezes_done:
            return
        self._zone.reset()


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
        self._time: Optional[float] = None
        self._timeout_handler: Optional[asyncio.Handle] = None
        self._wait_zone: asyncio.Event = asyncio.Event()
        self._state: _State = _State.INIT

    async def __aenter__(self) -> _TaskGlobal:
        self._manager.global_tasks.append(self)
        self._start_timer()
        self._state = _State.ENTER
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> Optional[bool]:
        self._stop_timer()
        self._manager.global_tasks.remove(self)

        # Timeout on exit
        if exc_type is asyncio.CancelledError and self.state == _State.TIMEOUT:
            raise asyncio.TimeoutError

        self._state == _State.EXIT
        self._wait_zone.set()
        return None

    @property
    def state(self) -> _State:
        """Return state of the Global task."""
        return self._state

    def zones_done_signal(self) -> None:
        """Signal that all zones are done."""
        self._wait_zone.set()

    def _start_timer(self) -> None:
        """Start timeout handler."""
        self._time = self._loop.time() + self._timeout
        self._timeout_handler = self._loop.call_at(self._time, self._on_timeout)

    def _stop_timer(self) -> None:
        """Stop zone timer."""
        if self._timeout_handler is None:
            return

        self._timeout_handler.cancel()
        self._timeout_handler = None
        # Calculate new timeout
        self._timeout = self._time - self._loop.time()

    def _on_timeout(self) -> None:
        """Process timeout."""
        self._state = _State.TIMEOUT
        self._timeout_handler = None

        # Reset timer if zones are running
        if not self._manager.zones_done:
            asyncio.create_task(self._on_wait())
        else:
            self._cancel_task()

    def _cancel_task(self) -> None:
        """Cancel own task."""
        if self._task.done():
            return
        self._task.cancel()

    def pause(self) -> None:
        """Pause timers while it freeze."""
        self._stop_timer()

    def reset(self) -> None:
        """Reset timer after freeze."""
        self._start_timer()

    async def _on_wait(self) -> None:
        """Wait until zones are done."""
        await self._wait_zone.wait()
        await asyncio.sleep(0)  # Allow context switch
        if not self.state == _State.TIMEOUT:
            return
        self._cancel_task()


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
        self._task.cancel()

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
        self._freezes: List[_FreezeZone] = []
        self._timeout: float = timeout
        self._time: Optional[float] = None
        self._state: _State = _State.INIT
        self._count: int = 0
        self._timeout_handler: Optional[asyncio.Handle] = None

    @property
    def name(self) -> str:
        """Return Zone name."""
        return self._zone

    @property
    def state(self) -> _State:
        """Return state of the Zone."""
        return self._state

    @property
    def freezes(self) -> List[_FreezeZone]:
        """Return list of zone freezes."""
        return self._freezes

    @property
    def freezes_done(self) -> bool:
        """Return True if all freeze are done."""
        return len(self._freezes) == 0 and self._manager.freezes_done

    def enter_task(self, task: _TaskZone) -> None:
        """Start into new Task."""
        if self.state == _State.TIMEOUT:
            raise asyncio.TimeoutError
        elif self.state != _State.ENTER:
            self._start_timer()

        self._count += 1
        self._tasks.append(task)

    def exit_task(self, task: _TaskZone, exc_type: Type[BaseException]) -> None:
        """Exit a running Task."""
        self._count -= 1

        # Timeout exit
        if exc_type is asyncio.CancelledError and self.state == _State.TIMEOUT:
            if self._count == 0:
                self._manager.drop_zone(self.name)
            raise asyncio.TimeoutError

        # On latest listener
        if self._count == 0 and self.state != _State.EXIT:
            self._state = _State.EXIT
            self._stop_timer()
            self._manager.drop_zone(self.name)

        self._tasks.remove(task)

    def _start_timer(self) -> None:
        """Start timeout handler."""
        self._state = _State.ENTER
        self._time = self._loop.time() + self._timeout
        self._timeout_handler = self._loop.call_at(self._time, self._on_timeout)

    def _stop_timer(self) -> None:
        """Stop zone timer."""
        if self._timeout_handler is None:
            return

        self._timeout_handler.cancel()
        self._timeout_handler = None
        # Calculate new timeout
        self._timeout = self._time - self._loop.time()

    def _on_timeout(self) -> None:
        """Process timeout."""
        self._timeout_handler = None
        self._state = _State.TIMEOUT

        # Cancel all running tasks
        for task in self._tasks:
            if task.done():
                continue
            task.cancel()

    def pause(self) -> None:
        """Stop timers while it freeze."""
        if self._state != _State.ENTER:
            return
        self._state = _State.FREEZE
        self._stop_timer()

    def reset(self) -> None:
        """Reset timer after freeze."""
        if self._state != _State.FREEZE:
            return
        self._state = _State.ENTER
        self._start_timer()


class ZoneTimeout:
    """Async zone based timeout handler."""

    def __init__(self):
        """Initalize ZoneTimeout handler."""
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self._zones: Dict[str, _Zone] = {}
        self._globals: List[_TaskGlobal] = []
        self._freezes: List[_FreezeGlobal] = []

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
        """Return all global Tasks."""
        return self._globals

    @property
    def global_freezes(self) -> List[_FreezeGlobal]:
        """Return all global Freezes."""
        return self._freezes

    def drop_zone(self, zone_name: str) -> None:
        """Drop a zone out of scope."""
        self._zones.pop(zone_name, None)
        if self._zones:
            return

        # Signal Global task, all zones are done
        for task in self._globals:
            task.zones_done_signal()

    def asnyc_timeout(
        self, timeout: float, zone_name: str = ZONE_GLOBAL
    ) -> Union[_TaskZone, _TaskGlobal]:
        """Timeout based on a zone.

        For using as Async Context Manager.
        """
        current_task: asyncio.Task[Any] = asyncio.current_task()

        # Global Zone
        if zone_name == ZONE_GLOBAL:
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

    def freeze(self, zone_name: str = ZONE_GLOBAL) -> Union[_FreezeZone, _FreezeGlobal]:
        """Freeze all timer until job is done.

        For using as (Async) Context Manager.
        """
        # Global Freeze
        if zone_name == ZONE_GLOBAL:
            return _FreezeGlobal(self, self._loop)

        # Zone Freeze
        if zone_name in self.zones:
            zone: _Zone = self.zones[zone_name]
            return _FreezeZone(zone, self._loop)

        # Should not happens...
        return _FreezeGlobal(self, self._loop)
