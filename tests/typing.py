"""Typing helpers for Home Assistant tests."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import MagicMock

from aiohttp import ClientWebSocketResponse
from aiohttp.test_utils import TestClient

ClientSessionGenerator = Callable[..., Coroutine[Any, Any, TestClient]]
MqttMockType = Callable[..., Coroutine[Any, Any, MagicMock]]
WebSocketGenerator = Callable[..., Coroutine[Any, Any, ClientWebSocketResponse]]
