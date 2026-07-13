"""Helpers for sending commands to iZone controllers."""

from collections.abc import Callable, Coroutine
import contextlib
from functools import wraps
import logging
from typing import Any, Concatenate, Protocol

from pizone import ControllerCommandError

_LOGGER = logging.getLogger(__name__)


class _IzoneAvailabilityDevice(Protocol):
    @property
    def device_uid(self) -> str: ...

    def set_available(self, available: bool, ex: Exception | None = None) -> None: ...


class _IzoneCommandEntity(Protocol):
    def _izone_availability_device(self) -> _IzoneAvailabilityDevice: ...


@contextlib.asynccontextmanager
async def izone_command_context(availability_device: _IzoneAvailabilityDevice):
    """Handle connection and command errors for a pizone controller command."""
    try:
        yield
    except ControllerCommandError as ex:
        _LOGGER.warning(
            "Controller %s rejected command: %s",
            availability_device.device_uid,
            ex,
        )
    except ConnectionError as ex:
        availability_device.set_available(False, ex)
    else:
        availability_device.set_available(True)


def send_izone_command[_EntityT: _IzoneCommandEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Wrap an entity command to handle pizone connection and command errors."""

    @wraps(func)
    async def handler(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        async with izone_command_context(self._izone_availability_device()):
            await func(self, *args, **kwargs)

    return handler
