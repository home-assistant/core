"""Decorators for ZHA core registries."""
from typing import Callable, TypeVar

CALLABLE_T = TypeVar("CALLABLE_T", bound=Callable)  # noqa pylint: disable=invalid-name


class DictRegistry(dict):
    """Dict Registry of items."""

    def register(self, channel: CALLABLE_T) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Register channel."""

        if hasattr(channel, "CLUSTER_ID") and channel.CLUSTER_ID is not None:
            self[channel.CLUSTER_ID] = channel

        return channel


class SetRegistry(set):
    """Set Registry of items."""

    def register(self, channel: CALLABLE_T) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Register channel cluster id."""

        if hasattr(channel, "CLUSTER_ID") and channel.CLUSTER_ID is not None:
            self.add(channel.CLUSTER_ID)

        return channel
