"""Tests for the Elke27 hub."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

_elke27_lib = ModuleType("elke27_lib")
_elke27_lib_errors = ModuleType("elke27_lib.errors")


class Elke27Error(Exception):
    """Base Elke27 error."""


class Elke27ConnectionError(Elke27Error):
    """Connection error stub."""


class Elke27AuthError(Elke27Error):
    """Auth error stub."""


class Elke27TimeoutError(Elke27Error):
    """Timeout error stub."""


class Elke27DisconnectedError(Elke27Error):
    """Disconnected error stub."""


class Elke27LinkRequiredError(Elke27Error):
    """Link required stub."""


class AuthorizationRequired(Elke27Error):
    """Authorization required stub."""


class Elke27PermissionError(Elke27Error):
    """Permission error stub."""


class InvalidCredentials(Elke27AuthError):
    """Invalid credentials stub."""


class InvalidPin(Elke27AuthError):
    """Invalid PIN stub."""


class InvalidPinError(Elke27AuthError):
    """Invalid PIN error stub."""


class MissingPinError(Elke27AuthError):
    """Missing PIN error stub."""


class ArmMode(Enum):
    """Stub arm modes."""

    DISARMED = "disarmed"
    ARMED_STAY = "armed_stay"
    ARMED_AWAY = "armed_away"
    ARMED_NIGHT = "armed_night"


_elke27_lib_errors.Elke27Error = Elke27Error
_elke27_lib_errors.Elke27ConnectionError = Elke27ConnectionError
_elke27_lib_errors.Elke27AuthError = Elke27AuthError
_elke27_lib_errors.Elke27TimeoutError = Elke27TimeoutError
_elke27_lib_errors.Elke27DisconnectedError = Elke27DisconnectedError
_elke27_lib_errors.Elke27LinkRequiredError = Elke27LinkRequiredError
_elke27_lib_errors.AuthorizationRequired = AuthorizationRequired
_elke27_lib_errors.Elke27PermissionError = Elke27PermissionError
_elke27_lib_errors.InvalidCredentials = InvalidCredentials
_elke27_lib_errors.InvalidPin = InvalidPin
_elke27_lib_errors.InvalidPinError = InvalidPinError
_elke27_lib_errors.MissingPinError = MissingPinError


@dataclass(frozen=True, slots=True)
class FakeClientConfig:
    """Minimal config stub."""


@dataclass(frozen=True, slots=True)
class FakeLinkKeys:
    """Minimal link keys stub."""

    payload: str

    @classmethod
    def from_json(cls, payload: str) -> "FakeLinkKeys":
        """Return stub link keys from JSON."""
        return cls(payload)


_elke27_lib.ClientConfig = FakeClientConfig
_elke27_lib.LinkKeys = FakeLinkKeys
_elke27_lib.Elke27Client = object
_elke27_lib.DiscoveredPanel = object
_elke27_lib.ArmMode = ArmMode

sys.modules["elke27_lib"] = _elke27_lib
sys.modules["elke27_lib.errors"] = _elke27_lib_errors

from homeassistant.components.elke27.const import READY_TIMEOUT
from homeassistant.components.elke27.hub import Elke27Hub
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


def _client_factory(client: AsyncMock) -> callable:
    def _factory(*args, **kwargs):
        assert not kwargs
        assert len(args) == 1
        return client

    return _factory


async def test_start_connects_and_subscribes(hass: HomeAssistant) -> None:
    """Test hub start connects, waits, and subscribes."""
    client = AsyncMock()
    client.async_connect = AsyncMock(return_value=None)
    client.async_discover = AsyncMock(
        return_value=[SimpleNamespace(panel_name="Panel A")]
    )
    client.wait_ready = AsyncMock(return_value=True)
    client.async_disconnect = AsyncMock(return_value=None)
    client.snapshot = object()
    unsubscribe = Mock()
    client.subscribe = Mock(return_value=unsubscribe)

    with patch(
        "homeassistant.components.elke27.hub.Elke27Client",
        side_effect=_client_factory(client),
    ):
        hub = Elke27Hub(
            hass, "192.168.1.70", 2101, "link-keys-json", "112233445566", None, None
        )
        await hub.async_start()

    client.async_connect.assert_awaited_once()
    client.wait_ready.assert_awaited_once_with(timeout_s=READY_TIMEOUT)
    client.subscribe.assert_called_once()
    assert hub.snapshot is client.snapshot

    await hub.async_stop()
    unsubscribe.assert_called_once()
    client.async_disconnect.assert_awaited_once()


async def test_start_wait_ready_false_disconnects(hass: HomeAssistant) -> None:
    """Test hub start disconnects when ready is false."""
    client = AsyncMock()
    client.async_connect = AsyncMock(return_value=None)
    client.async_discover = AsyncMock(return_value=[])
    client.wait_ready = AsyncMock(return_value=False)
    client.async_disconnect = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.elke27.hub.Elke27Client",
        side_effect=_client_factory(client),
    ):
        hub = Elke27Hub(
            hass, "192.168.1.71", 2101, "link-keys-json", "112233445566", None, None
        )
        with pytest.raises(ConfigEntryNotReady):
            await hub.async_start()

    client.async_disconnect.assert_awaited_once()


async def test_event_routing_updates_snapshot(hass: HomeAssistant) -> None:
    """Test event routing updates snapshot and notifies listeners."""
    client = AsyncMock()
    client.async_connect = AsyncMock(return_value=None)
    client.async_discover = AsyncMock(return_value=[])
    client.wait_ready = AsyncMock(return_value=True)
    client.async_disconnect = AsyncMock(return_value=None)
    first_snapshot = object()
    second_snapshot = object()
    client.snapshot = first_snapshot
    client.subscribe = Mock(return_value=Mock())

    with patch(
        "homeassistant.components.elke27.hub.Elke27Client",
        side_effect=_client_factory(client),
    ):
        hub = Elke27Hub(
            hass, "192.168.1.72", 2101, "link-keys-json", "112233445566", None, None
        )
        await hub.async_start()

    general_calls: list[str] = []
    area_calls: list[str] = []
    zone_calls: list[str] = []
    output_calls: list[str] = []
    system_calls: list[str] = []

    hub.async_add_listener(lambda: general_calls.append("all"))
    hub.async_add_area_listener(lambda: area_calls.append("area"))
    hub.async_add_zone_listener(lambda: zone_calls.append("zone"))
    hub.async_add_output_listener(lambda: output_calls.append("output"))
    hub.async_add_system_listener(lambda: system_calls.append("system"))

    client.snapshot = second_snapshot
    hub._handle_event({"type": "AREA"})
    await hass.async_block_till_done()

    assert hub.snapshot is second_snapshot
    assert general_calls == ["all"]
    assert area_calls == ["area"]
    assert zone_calls == []
    assert output_calls == []
    assert system_calls == []

    hub._handle_event({"type": "SYSTEM"})
    await hass.async_block_till_done()
    assert system_calls == ["system"]

    await hub.async_stop()
