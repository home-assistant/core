"""Shard test definitions."""

from collections.abc import Awaitable, Callable
from datetime import timedelta

type TriggerPollFunc = Callable[[timedelta], Awaitable[None]]
type InitIntegrationFunc = Callable[[], Awaitable[bool]]
