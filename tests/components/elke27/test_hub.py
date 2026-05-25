"""Tests for the Elke27 hub."""

import asyncio
from collections.abc import Callable
from enum import Enum
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from elke27_lib import ArmMode, LinkKeys
from elke27_lib.errors import (
    Elke27InvalidArgument,
    Elke27LinkRequiredError,
    Elke27PinRequiredError,
)
import pytest

from homeassistant.components.elke27.const import READY_TIMEOUT
from homeassistant.components.elke27.hub import (
    Elke27Hub,
    _connection_state,
    _event_type,
    _set_client_identity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError


def _client_factory(client: AsyncMock) -> Callable[..., AsyncMock]:
    def _factory(*args, **kwargs):
        assert not kwargs
        assert len(args) == 1
        return client

    return _factory


async def test_connect_subscribes_and_disconnects(hass: HomeAssistant) -> None:
    """Test hub connect subscribes and disconnects cleanly."""
    client = AsyncMock()
    client.async_connect = AsyncMock(return_value=None)
    client.set_client_identity = Mock()
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
    client.set_client_identity.assert_called_once_with(
        {"mn": "222", "sn": "112233445566"}
    )
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
    client.set_client_identity = Mock()
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


async def test_connect_replaces_client_without_unavailable_log(
    hass: HomeAssistant,
) -> None:
    """Test intentional reconnect replacement does not log unavailable."""
    old_client = SimpleNamespace(async_disconnect=AsyncMock(return_value=None))
    new_client = AsyncMock()
    new_client.async_connect = AsyncMock(return_value=None)
    new_client.set_client_identity = Mock()
    new_client.wait_ready = AsyncMock(return_value=True)
    new_client.subscribe = Mock(return_value=Mock())

    hub = Elke27Hub(
        hass,
        "192.168.1.71",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._client = old_client

    with (
        patch(
            "homeassistant.components.elke27.hub.Elke27Client",
            side_effect=_client_factory(new_client),
        ),
        patch.object(hub, "_log_unavailable") as log_unavailable,
    ):
        await hub.async_connect()

    old_client.async_disconnect.assert_awaited_once()
    log_unavailable.assert_not_called()


async def test_refresh_and_subscribe_errors(hass: HomeAssistant) -> None:
    """Verify refresh methods and subscribe error when disconnected."""
    hub = Elke27Hub(
        hass,
        "192.168.1.72",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    with pytest.raises(HomeAssistantError):
        await hub.refresh_csm()
    with pytest.raises(HomeAssistantError):
        await hub.refresh_domain_config("zone")

    def _listener(*_args: Any) -> None:
        return None

    with pytest.raises(HomeAssistantError):
        hub.subscribe(_listener)


async def test_area_commands_return_false_when_no_client(
    hass: HomeAssistant,
) -> None:
    """Verify area command methods return False when no client is set."""
    hub = Elke27Hub(
        hass,
        "192.168.1.72",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    assert await hub.async_set_zone_bypass(1, bypassed=True, pin="1234") is False
    assert await hub.async_arm_area(1, "ARMED_AWAY", pin="1234") is False
    assert await hub.async_disarm_area(1, pin="1234") is False


async def test_connect_clears_unavailable_log(hass: HomeAssistant) -> None:
    """Verify connect clears unavailable log."""
    client = AsyncMock()
    client.async_connect = AsyncMock(return_value=None)
    client.wait_ready = AsyncMock(return_value=True)
    client.async_disconnect = AsyncMock(return_value=None)
    client.subscribe = Mock(return_value=Mock())
    client.set_client_identity = Mock()

    with patch(
        "homeassistant.components.elke27.hub.Elke27Client",
        side_effect=_client_factory(client),
    ):
        hub = Elke27Hub(
            hass,
            "192.168.1.72",
            2101,
            LinkKeys("tk", "lk", "lh").to_json(),
            "112233445566",
            None,
        )
        hub._unavailable_logged = True
        await hub.async_connect()
        assert hub._unavailable_logged is False


async def test_hub_properties(hass: HomeAssistant) -> None:
    """Verify basic hub properties."""
    hub = Elke27Hub(
        hass,
        "192.168.1.80",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        "Panel",
    )
    assert hub.panel_name == "Panel"
    assert hub.is_ready is False
    hub._client = SimpleNamespace(is_ready=True)
    assert hub.is_ready is True
    assert hub.client is hub._client


async def test_async_disconnect_cancels_reconnect_task(hass: HomeAssistant) -> None:
    """Verify async_disconnect cancels reconnect task."""
    hub = Elke27Hub(
        hass,
        "192.168.1.83",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._reconnect_task = asyncio.create_task(asyncio.sleep(0))
    await hub.async_disconnect()
    assert hub._reconnect_task is None


async def test_snapshot_and_refresh_paths(hass: HomeAssistant) -> None:
    """Verify snapshot and refresh paths with client."""
    client = SimpleNamespace(
        get_snapshot=Mock(return_value="snap"),
        async_refresh_csm=AsyncMock(return_value="ok"),
        async_refresh_domain_config=AsyncMock(return_value=None),
    )
    hub = Elke27Hub(
        hass,
        "192.168.1.84",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._client = client
    assert hub.get_snapshot() == "snap"
    assert await hub.refresh_csm() == "ok"
    await hub.refresh_domain_config("zone")
    client.async_refresh_domain_config.assert_awaited_once_with("zone")


async def test_get_snapshot_no_client(hass: HomeAssistant) -> None:
    """Verify get_snapshot returns None without client."""
    hub = Elke27Hub(
        hass,
        "192.168.1.95",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    assert hub.get_snapshot() is None


async def test_subscribe_and_unsubscribe_typed_client(hass: HomeAssistant) -> None:
    """Verify subscribe and unsubscribe via client."""
    client = SimpleNamespace(
        subscribe=Mock(return_value="token"),
        unsubscribe_typed=Mock(return_value=True),
    )
    hub = Elke27Hub(
        hass,
        "192.168.1.85",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._client = client
    assert hub.subscribe(lambda *_: None) == "token"
    assert hub.unsubscribe_typed(lambda *_: None) is True


async def test_zone_bypass_error_none(hass: HomeAssistant) -> None:
    """Verify zone bypass returns False without a client and True on success."""
    hub = Elke27Hub(
        hass,
        "192.168.1.87",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    assert await hub.async_set_zone_bypass(1, bypassed=True, pin="1234") is False
    hub._client = SimpleNamespace(async_set_zone_bypass=AsyncMock(return_value=None))
    assert await hub.async_set_zone_bypass(1, bypassed=True, pin="1234") is True


async def test_arm_area_modes_and_errors(hass: HomeAssistant) -> None:
    """Verify arm modes and error handling."""
    hub = Elke27Hub(
        hass,
        "192.168.1.88",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    client = SimpleNamespace(async_arm_area=AsyncMock(return_value=None))
    hub._client = client
    assert await hub.async_arm_area(1, ArmMode.ARMED_STAY, "1234") is True
    assert await hub.async_arm_area(1, ArmMode.ARMED_NIGHT, "1234") is True
    assert await hub.async_arm_area(1, "ARMED_CUSTOM_BYPASS", "1234") is True
    assert await hub.async_arm_area(1, "ARMED_NIGHT", "1234") is True
    assert (
        client.async_arm_area.await_args_list[1].kwargs["mode"] is ArmMode.ARMED_NIGHT
    )

    hub._client = SimpleNamespace(
        async_arm_area=AsyncMock(side_effect=Elke27InvalidArgument("nope"))
    )
    with pytest.raises(HomeAssistantError, match="nope"):
        await hub.async_arm_area(1, ArmMode.ARMED_AWAY, "1234")

    hub._client = None
    assert await hub.async_arm_area(1, ArmMode.ARMED_AWAY, "1234") is False


async def test_resubscribe_typed_callbacks(hass: HomeAssistant) -> None:
    """Verify resubscribe updates callbacks."""
    hub = Elke27Hub(
        hass,
        "192.168.1.89",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )

    def _cb(*_args: Any) -> None:
        return None

    cb = _cb
    hub._typed_callbacks = {cb: None}
    client = SimpleNamespace(subscribe_typed=Mock(return_value="token"))
    hub._client = client
    hub._resubscribe_typed_callbacks()
    assert hub._typed_callbacks[cb] == "token"


async def test_disarm_pin_and_error_none(hass: HomeAssistant) -> None:
    """Verify disarm handles pin errors and ok false with no error."""
    hub = Elke27Hub(
        hass,
        "192.168.1.90",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._client = SimpleNamespace(async_disarm_area=AsyncMock(return_value=None))
    with pytest.raises(Elke27PinRequiredError, match=r"PIN=.*required to disarm areas"):
        await hub.async_disarm_area(1, None)
    hub._client.async_disarm_area.side_effect = Elke27InvalidArgument(
        "PIN must be a non-empty digit string."
    )
    with pytest.raises(
        HomeAssistantError, match="PIN=.*must be a non-empty digit string"
    ):
        await hub.async_disarm_area(1, "aa")
    hub._client.async_disarm_area.side_effect = None
    assert await hub.async_disarm_area(1, "1234") is True


async def test_handle_connection_event_no_client(hass: HomeAssistant) -> None:
    """Verify handle_connection_event returns when no client."""
    hub = Elke27Hub(
        hass,
        "192.168.1.91",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._client = None
    hub._handle_connection_event({"event_type": "disconnected"})


async def test_schedule_reconnect_creates_task(hass: HomeAssistant) -> None:
    """Verify reconnect scheduling creates task."""
    hub = Elke27Hub(
        hass,
        "192.168.1.92",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    task = Mock()
    hub._hass.async_create_task = Mock(side_effect=lambda coro: (coro.close(), task)[1])
    hub._schedule_reconnect()
    assert hub._reconnect_task is task


async def test_log_unavailable_skips_when_logged(hass: HomeAssistant) -> None:
    """Verify log_unavailable skips when already logged."""
    hub = Elke27Hub(
        hass,
        "192.168.1.93",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._unavailable_logged = True
    hub._log_unavailable()


async def test_reconnect_loop_exception_path(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify reconnect loop handles expected connection exceptions and delays."""
    hub = Elke27Hub(
        hass,
        "192.168.1.94",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )

    async def _connect_fail():
        hub._stopping = True
        raise ConfigEntryNotReady("boom")

    hub._async_connect = _connect_fail
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))
    await hub._async_reconnect_loop()


async def test_reconnect_loop_reraises_unexpected_errors(
    hass: HomeAssistant,
) -> None:
    """Verify reconnect loop does not swallow unexpected errors."""
    hub = Elke27Hub(
        hass,
        "192.168.1.94",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._async_connect = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await hub._async_reconnect_loop()


async def test_reconnect_loop_success_resets_attempts(hass: HomeAssistant) -> None:
    """Verify reconnect loop resets attempts after success."""
    hub = Elke27Hub(
        hass,
        "192.168.1.96",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._reconnect_attempts = 2
    hub._async_connect = AsyncMock(return_value=None)
    await hub._async_reconnect_loop()
    assert hub._reconnect_attempts == 0


def test_event_type_and_connection_state_extra() -> None:
    """Verify additional event parsing paths."""
    assert _connection_state({"event_type": "disconnected"}) is False
    assert _connection_state({"event_type": "ready"}) is True
    event = SimpleNamespace(event_type="connection", data={"connected": True})
    assert _connection_state(event) is True
    event = SimpleNamespace(event_type="other")
    assert _connection_state(event) is None
    event = SimpleNamespace(connected=True)
    assert _connection_state(event) is True
    event = SimpleNamespace(connected="no")
    assert _connection_state(event) is None
    event = SimpleNamespace(event_type="disconnected")
    assert _connection_state(event) is False
    event = SimpleNamespace()
    assert _event_type(event) is None


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
        async_set_zone_bypass=AsyncMock(side_effect=Elke27InvalidArgument("bad"))
    )
    with pytest.raises(Exception, match=r"PIN=.*required to bypass zones"):
        await hub.async_set_zone_bypass(1, bypassed=True, pin=None)
    hub._client.async_set_zone_bypass.side_effect = Elke27InvalidArgument(
        "PIN must be a non-empty digit string."
    )
    with pytest.raises(
        HomeAssistantError, match="PIN=.*must be a non-empty digit string"
    ):
        await hub.async_set_zone_bypass(1, bypassed=True, pin="aa")
    hub._client.async_set_zone_bypass.side_effect = Elke27InvalidArgument("bad")
    with pytest.raises(HomeAssistantError, match="bad"):
        await hub.async_set_zone_bypass(1, bypassed=True, pin="1234")


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
    hub._client = SimpleNamespace(async_arm_area=AsyncMock(return_value=None))
    with pytest.raises(Exception, match=r"PIN=.*required to arm areas"):
        await hub.async_arm_area(1, "ARMED_AWAY", pin=None)
    hub._client.async_arm_area.side_effect = Elke27InvalidArgument(
        "PIN must be a non-empty digit string."
    )
    with pytest.raises(
        HomeAssistantError, match="PIN=.*must be a non-empty digit string"
    ):
        await hub.async_arm_area(1, "ARMED_AWAY", pin="aa")
    with pytest.raises(HomeAssistantError, match="Arm mode is not supported"):
        await hub.async_arm_area(1, "UNKNOWN_MODE", pin="1234")
    hub._client = None
    assert await hub.async_arm_area(1, "ARMED_NIGHT", pin="1234") is False
    hub._client = SimpleNamespace(
        async_disarm_area=AsyncMock(side_effect=Elke27InvalidArgument("nope"))
    )
    with pytest.raises(HomeAssistantError):
        await hub.async_disarm_area(1, pin="1234")


async def test_async_arm_area_uses_client_method(
    hass: HomeAssistant,
) -> None:
    """Verify arm requests use direct client methods when available."""
    hub = Elke27Hub(
        hass,
        "192.168.1.75",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    calls: list[Any] = []
    hub._client = SimpleNamespace(async_arm_area=_async_arm_area(calls))

    assert (
        await hub.async_arm_area(
            1,
            ArmMode.ARMED_AWAY,
            "1234",
            auto_stay_cancel=True,
            exit_delay_cancel=True,
        )
        is True
    )
    assert calls == [(1, ArmMode.ARMED_AWAY, "1234", True, True)]


def _async_arm_area(calls: list[Any]) -> Any:
    async def _method(
        area_id: int,
        *,
        mode: ArmMode,
        pin: str,
        auto_stay_cancel: bool,
        exit_delay_cancel: bool,
    ) -> None:
        calls.append((area_id, mode, pin, auto_stay_cancel, exit_delay_cancel))

    return _method


async def test_async_disarm_area_uses_client_method(
    hass: HomeAssistant,
) -> None:
    """Verify disarm requests use direct client methods when available."""
    hub = Elke27Hub(
        hass,
        "192.168.1.75",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    calls: list[Any] = []
    hub._client = SimpleNamespace(async_disarm_area=_async_disarm_area(calls))

    assert (
        await hub.async_disarm_area(
            1,
            "1234",
            auto_stay_cancel=True,
            exit_delay_cancel=True,
        )
        is True
    )
    assert calls == [(1, "1234", True, True)]


def _async_disarm_area(calls: list[Any]) -> Any:
    async def _method(
        area_id: int,
        pin: str,
        *,
        auto_stay_cancel: bool,
        exit_delay_cancel: bool,
    ) -> None:
        calls.append((area_id, pin, auto_stay_cancel, exit_delay_cancel))

    return _method


def test_set_client_identity_sets_identity() -> None:
    """Verify client identity setter is called."""
    client = SimpleNamespace(set_client_identity=Mock(return_value=None))

    _set_client_identity(client, {"mn": "222", "sn": "112233445566"})

    client.set_client_identity.assert_called_once_with(
        {"mn": "222", "sn": "112233445566"}
    )


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
    assert (
        _connection_state({"event_type": "connection", "data": {"connected": True}})
        is True
    )
    assert _connection_state(SimpleNamespace(event_type="ready")) is True
    enum_val = Enum("E", {"READY": "ready"})
    assert _event_type({"type": enum_val.READY}) == "READY"
    assert _connection_state({"event_type": None}) is None
    event = SimpleNamespace(type=enum_val.READY)
    assert _event_type(event) == "READY"
    event = SimpleNamespace(type="ready")
    assert _event_type(event) == "READY"


async def test_disconnect_clears_typed_subscriptions(hass: HomeAssistant) -> None:
    """Verify typed subscriptions are cleared on disconnect."""
    hub = Elke27Hub(
        hass,
        "192.168.1.79",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    unsubscribe = Mock()
    hub._typed_callbacks = {lambda *_: None: unsubscribe}
    hub._client = SimpleNamespace(async_disconnect=AsyncMock(return_value=None))
    await hub._async_disconnect()
    unsubscribe.assert_called_once()


async def test_disconnect_suppresses_client_disconnect_errors(
    hass: HomeAssistant,
) -> None:
    """Verify disconnect cleanup continues when the client raises."""
    hub = Elke27Hub(
        hass,
        "192.168.1.80",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    unsubscribe = Mock()
    hub._typed_callbacks = {lambda *_: None: unsubscribe}
    hub._client = SimpleNamespace(
        async_disconnect=AsyncMock(side_effect=RuntimeError("boom"))
    )

    await hub._async_disconnect()

    assert hub._client is None
    unsubscribe.assert_called_once()


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
    remove_duplicate = hub.subscribe_typed(callback)
    client.subscribe_typed.assert_called_once_with(callback)
    assert callable(remove)
    assert callable(remove_duplicate)
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
    await hass.async_block_till_done()
    hub._schedule_reconnect.assert_called_once()

    hub._handle_connection_event({"event_type": "ready"})
    await hass.async_block_till_done()
    hub._cancel_reconnect.assert_called_once()


async def test_reconnect_scheduling_guards(hass: HomeAssistant) -> None:
    """Verify reconnect scheduling guards."""
    hub = Elke27Hub(
        hass,
        "192.168.1.81",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._stopping = True
    hub._schedule_reconnect()
    hub._stopping = False
    hub._reconnect_task = Mock()
    hub._reconnect_task.done.return_value = False
    hub._schedule_reconnect()


async def test_cancel_reconnect(hass: HomeAssistant) -> None:
    """Verify cancel reconnect handles task state."""
    hub = Elke27Hub(
        hass,
        "192.168.1.82",
        2101,
        LinkKeys("tk", "lk", "lh").to_json(),
        "112233445566",
        None,
    )
    hub._cancel_reconnect()
    hub._reconnect_task = Mock()
    hub._reconnect_task.done.return_value = False
    hub._cancel_reconnect()
