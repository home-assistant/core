"""Event handler abstract class."""
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import Any

from .channel import HausbusChannel


class IEventHandler(ABC):
    """Abstract base class for gateway event handling."""

    @abstractmethod
    def register_platform_add_channel_callback(
        self,
        add_channel_callback: Callable[[HausbusChannel], Coroutine[Any, Any, None]],
        platform: str,
    ):
        """Register add device callbacks."""
        raise NotImplementedError
