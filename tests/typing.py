"""Typing helpers for Home Assistant tests."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import MagicMock

from aiohttp import ClientWebSocketResponse
from aiohttp.test_utils import TestClient

ClientSessionGenerator = Callable[..., Coroutine[Any, Any, TestClient]]
MqttMockPahoClient = MagicMock
"""MagicMock for `paho.mqtt.client.Client`"""
MqttMockHAClient = MagicMock
"""MagicMock for `homeassistant.components.mqtt.MQTT`."""
MqttMockHAClientGenerator = Callable[..., Coroutine[Any, Any, MqttMockHAClient]]
"""MagicMock generator for `homeassistant.components.mqtt.MQTT`."""
WebSocketGenerator = Callable[..., Coroutine[Any, Any, ClientWebSocketResponse]]
