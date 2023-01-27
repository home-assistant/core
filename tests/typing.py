"""Typing helpers for Home Assistant tests."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from aiohttp import ClientWebSocketResponse
from aiohttp.test_utils import TestClient

TestClientGenerator = Callable[..., Coroutine[Any, Any, TestClient]]
TestWebSocketGenerator = Callable[..., Coroutine[Any, Any, ClientWebSocketResponse]]
