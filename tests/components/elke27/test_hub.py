"""Tests for the Elke27 hub."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from elke27_lib import LinkKeys
from elke27_lib.errors import Elke27LinkRequiredError
import pytest

from homeassistant.components.elke27.const import READY_TIMEOUT
from homeassistant.components.elke27.hub import (
    Elke27Hub,
    _connection_state,
    _event_type,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


def _client_factory(client: AsyncMock) -> callable:
    def _factory(*args, **kwargs):
        assert not kwargs
        assert len(args) == 1
        return client

    return _factory


async def test_connect_subscribes_and_disconnects(hass: HomeAssistant) -> None:
    """Test hub connect subscribes and disconnects cleanly."""
    client = AsyncMock()
    client.async_connect = AsyncMock(return_value=None)
    client.async_discover = AsyncMock(
        return_value=[SimpleNamespace(panel_name="Panel A")]
    )
    client._coerce_identity = lambda identity: identity
    client.wait_ready = AsyncMock(return_value=True)
    client.async_disconnect = AsyncMock(return_value=None)
    unsubscribe = Mock()
    client.subscribe = Mock(return_value=unsubscribe)

    with patch(
        "homeassistant.components.elke27.hub.Elke27Client",
        side_effect=_client_factory(client),
    ):
        hub = Elke27Hub(
            hass,
            "192.168.1.70",
            2101,
            LinkKeys("tk", "lk", "lh").to_json(),
            "112233445566",
            None,
        )
        await hub.async_connect()

    client.async_connect.assert_awaited_once()
    client.wait_ready.assert_awaited_once_with(timeout_s=READY_TIMEOUT)
    client.subscribe.assert_called_once()

    await hub.async_disconnect()
    unsubscribe.assert_called_once()
    client.async_disconnect.assert_awaited_once()


async def test_connect_wait_ready_false_disconnects(
    hass: HomeAssistant,
) -> None:
    """Test hub connect disconnects when ready is false."""
    client = AsyncMock()
    client.async_connect = AsyncMock(return_value=None)
    client.async_discover = AsyncMock(return_value=[])
    client._coerce_identity = lambda identity: identity
    client.wait_ready = AsyncMock(return_value=False)
    client.async_disconnect = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.elke27.hub.Elke27Client",
        side_effect=_client_factory(client),
    ):
        hub = Elke27Hub(
            hass,
            "192.168.1.71",
            2101,
            LinkKeys("tk", "lk", "lh").to_json(),
            "112233445566",
            None,
        )
        with pytest.raises(ConfigEntryNotReady):
            await hub.async_connect()

    client.async_disconnect.assert_awaited_once()


async def test_async_set_output_supports_async_and_sync(
    hass: HomeAssistant,
) -> None:
    """Verify output commands use async or sync client methods."""
    hub = Elke27Hub(
        hass,
        "192.168.1.72",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    async def _async_set(output_id: int, *, on: bool) -> bool:
        assert output_id == 1
        return on

    def _sync_set(output_id: int, state: bool) -> bool:
        assert output_id == 2
        return state

    hub._client = SimpleNamespace(async_set_output=_async_set)
    assert await hub.async_set_output(1, True) is True

    hub._client = SimpleNamespace(set_output=_sync_set)
    assert await hub.async_set_output(2, False) is False


async def test_async_set_output_missing_method(
    hass: HomeAssistant,
) -> None:
    """Verify output commands return false when unsupported."""
    hub = Elke27Hub(
        hass,
        "192.168.1.73",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._client = SimpleNamespace()
    assert await hub.async_set_output(1, True) is False


async def test_zone_bypass_validation_and_errors(
    hass: HomeAssistant,
) -> None:
    """Verify zone bypass validates PIN and surfaces errors."""
    hub = Elke27Hub(
        hass,
        "192.168.1.74",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._client = SimpleNamespace(
        async_execute=AsyncMock(return_value=SimpleNamespace(ok=False, error=ValueError("bad")))
    )
    with pytest.raises(Exception, match="PIN required"):
        await hub.async_set_zone_bypass(1, True, pin=None)
    with pytest.raises(Exception, match="Code must be numeric"):
        await hub.async_set_zone_bypass(1, True, pin="aa")
    with pytest.raises(Exception):
        await hub.async_set_zone_bypass(1, True, pin="1234")


async def test_arm_and_disarm_area_errors(
    hass: HomeAssistant,
) -> None:
    """Verify area arm/disarm handles unsupported modes and errors."""
    hub = Elke27Hub(
        hass,
        "192.168.1.75",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._client = SimpleNamespace(
        async_execute=AsyncMock(return_value=SimpleNamespace(ok=False, error=ValueError("nope")))
    )
    with pytest.raises(Exception, match="PIN required"):
        await hub.async_arm_area(1, "ARMED_AWAY", pin=None)
    with pytest.raises(Exception, match="Code must be numeric"):
        await hub.async_arm_area(1, "ARMED_AWAY", pin="aa")
    with pytest.raises(Exception, match="Arm mode is not supported"):
        await hub.async_arm_area(1, "ARMED_NIGHT", pin="1234")
    with pytest.raises(Exception):
        await hub.async_disarm_area(1, pin="1234")


async def test_reconnect_loop_stops_on_link_required(
    hass: HomeAssistant,
) -> None:
    """Verify reconnect loop stops on link required errors."""
    hub = Elke27Hub(
        hass,
        "192.168.1.76",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._async_connect = AsyncMock(side_effect=Elke27LinkRequiredError("nope"))
    await hub._async_reconnect_loop()


def test_event_type_and_connection_state() -> None:
    """Verify event helpers handle dict and object values."""
    assert _event_type({"type": "ready"}) == "READY"
    assert _event_type(SimpleNamespace(event_type="disconnected")) == "DISCONNECTED"
    assert _connection_state({"event_type": "connection", "data": {"connected": True}}) is True
    assert _connection_state(SimpleNamespace(event_type="ready")) is True


async def test_subscribe_typed_and_unsubscribe(hass: HomeAssistant) -> None:
    """Verify typed subscriptions register and unregister callbacks."""
    hub = Elke27Hub(
        hass,
        "192.168.1.77",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    unsubscribe = Mock()
    client = SimpleNamespace(subscribe_typed=Mock(return_value=unsubscribe))
    hub._client = client

    callback = Mock()
    remove = hub.subscribe_typed(callback)
    assert callable(remove)
    remove()
    unsubscribe.assert_called_once()

    hub._client = None
    assert hub.unsubscribe_typed(Mock()) is False


async def test_handle_connection_event_triggers_reconnect(
    hass: HomeAssistant,
) -> None:
    """Verify disconnect and ready events schedule/cancel reconnect."""
    hub = Elke27Hub(
        hass,
        "192.168.1.78",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._client = SimpleNamespace()
    hub._schedule_reconnect = Mock()
    hub._cancel_reconnect = Mock()

    hub._handle_connection_event({"event_type": "disconnected"})
    hub._schedule_reconnect.assert_called_once()

    hub._handle_connection_event({"event_type": "ready"})
    hub._cancel_reconnect.assert_called_once()
