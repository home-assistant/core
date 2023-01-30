"""Typing helpers for Home Assistant tests."""
from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from typing import Any

    from aiohttp import ClientWebSocketResponse
    from aiohttp.test_utils import TestClient

TestClientGenerator: TypeAlias = "Callable[..., Coroutine[Any, Any, TestClient]]"
TestWebSocketGenerator: TypeAlias = (
    "Callable[..., Coroutine[Any, Any, ClientWebSocketResponse]]"
)
