"""Pytest configuration and fixtures for INELNET Blinds tests."""

from __future__ import annotations

from enum import IntEnum
import importlib.util
import sys
import types

# Stub inelnet_api only when the package is not installed (e.g. when not on PyPI)
if importlib.util.find_spec("inelnet_api") is None:

    class Action(IntEnum):
        """Stub Action enum matching inelnet_api.Action."""

        STOP = 144
        UP = 160
        UP_SHORT = 176
        DOWN = 192
        DOWN_SHORT = 208
        PROGRAM = 224

    class InelnetChannel:
        """Stub InelnetChannel for testing."""

        def __init__(self, host: str, channel: int) -> None:
            """Store host and channel for the stub."""
            self._host = host
            self._channel = channel

        @property
        def host(self) -> str:
            """Return stub host."""
            return self._host

        @property
        def channel(self) -> int:
            """Return stub channel."""
            return self._channel

        async def ping(self, *, session=None, timeout=None) -> bool:
            """Stub ping; always succeeds."""
            return True

        async def send_command(self, act, *, session=None, timeout=None) -> bool:
            """Stub send_command; always succeeds."""
            return True

        async def up(self, *, session=None, **kwargs) -> bool:
            """Stub up; always succeeds."""
            return True

        async def down(self, *, session=None, **kwargs) -> bool:
            """Stub down; always succeeds."""
            return True

        async def stop(self, *, session=None, **kwargs) -> bool:
            """Stub stop; always succeeds."""
            return True

    stub = types.ModuleType("inelnet_api")
    stub.Action = Action
    stub.InelnetChannel = InelnetChannel
    sys.modules["inelnet_api"] = stub
