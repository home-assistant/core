"""Decorators for the rasc integration."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING, Any, TypeVar, cast, overload

from homeassistant.helpers.entity import Entity

from .abstraction import RASC
from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import EntityPlatform
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
        rasc: RASC = self.hass.data[DOMAIN]
        await rasc.async_on_push_event(self)
        return rt

    return _wrapper


@overload
def rasc_track_service(func: Callable[..., Awaitable[RT]]):
    ...


@overload
def rasc_track_service(func: Callable[..., RT]):
    ...


def rasc_track_service(
    func: Callable[..., RT] | Callable[..., Awaitable[RT]]
) -> Callable[..., Coroutine[Any, Any, RT]]:
    """RASC decorator for tracking a service."""

    async def _wrapper(
        self: EntityPlatform | DataUpdateCoordinator,
        entity: Entity,
        *args: Any,
        **kwargs: dict[str, Any],
    ) -> RT:
        if asyncio.iscoroutinefunction(func):
            rt = await cast(Awaitable[RT], func(self, entity, *args, **kwargs))
        else:
            rt = cast(RT, func(self, entity, *args, **kwargs))
        rasc: RASC = self.hass.data[DOMAIN]
        await rasc.update(entity, self)
        return rt

    return _wrapper
