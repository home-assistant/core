"""Decorators for the rasc integration."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING, Any, TypeVar, cast, overload

from homeassistant.helpers.entity import Entity

from .const import DOMAIN

if TYPE_CHECKING:
    from .abstraction import RASCAbstraction

RT = TypeVar("RT")


@overload
def rasc_push_event(func: Callable[..., Awaitable[RT]]):
    ...


@overload
def rasc_push_event(func: Callable[..., RT]):
    ...


def rasc_push_event(
    func: Callable[..., RT] | Callable[..., Awaitable[RT]]
) -> Callable[..., Coroutine[Any, Any, RT]]:
    """RASC decorator for push-based devices."""

    async def _wrapper(self: Entity, *args: Any, **kwargs: dict[str, Any]) -> RT:
        if asyncio.iscoroutinefunction(func):
            rt = await cast(Awaitable[RT], func(self, *args, **kwargs))
        else:
            rt = cast(RT, func(self, *args, **kwargs))
        rasc: RASCAbstraction = self.hass.data[DOMAIN]
        await rasc.async_on_push_event(self)
        return rt

    return _wrapper


def rasc_target_state(
    target_complete_state: Any,
) -> Callable[[Callable[[Any], bool]], Callable[[Any], bool]]:
    """RASC decorator for match function."""

    def decorator(func: Callable[[Any], bool]) -> Callable[[Any], bool]:
        def wrapper(value: Any) -> bool:
            wrapper.value = target_complete_state  # type: ignore[attr-defined]
            return func(value)

        return wrapper

    return decorator


# @overload
# def rasc_track_service(func: Callable[..., Awaitable[RT]]):
#     ...


# @overload
# def rasc_track_service(func: Callable[..., RT]):
#     ...


# def rasc_track_service(
#     func: Callable[..., RT] | Callable[..., Awaitable[RT]]
# ) -> Callable[..., Coroutine[Any, Any, RT]]:
#     """RASC decorator for tracking a service."""

#     async def _wrapper(
#         self: EntityPlatform | DataUpdateCoordinator,
#         entity: Entity,
#         *args: Any,
#         **kwargs: dict[str, Any],
#     ) -> RT:
#         if asyncio.iscoroutinefunction(func):
#             rt = await cast(Awaitable[RT], func(self, entity, *args, **kwargs))
#         else:
#             rt = cast(RT, func(self, entity, *args, **kwargs))
#         rasc: RASCAbstraction = self.hass.data[DOMAIN]
#         await rasc.update(entity)
#         return rt

#     return _wrapper
