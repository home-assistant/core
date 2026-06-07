"""Tests for the coordinator (REST refresh + push event handling)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import socketio

from homeassistant.components.culiplan.api import CuliplanApiError
from homeassistant.components.culiplan.const import DOMAIN
from homeassistant.components.culiplan.coordinator import CuliplanCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def coordinator_pair(hass: HomeAssistant) -> tuple[CuliplanCoordinator, MagicMock]:
    """Return a coordinator wired to a mocked API client."""
    client = MagicMock()
    client.set_access_token = MagicMock()
    client.async_get_meal_plans = AsyncMock(return_value=[])
    client.async_get_shopping_lists = AsyncMock(return_value=[])
    client.async_get_pantry_items = AsyncMock(return_value=[])

    entry: ConfigEntry = MockConfigEntry(domain=DOMAIN, unique_id="u-1")
    entry.add_to_hass(hass)
    coordinator = CuliplanCoordinator(hass, client, entry)
    return coordinator, client


async def test_update_data_happy_path(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """``_async_update_data`` fetches all three slices."""
    coordinator, _client = coordinator_pair
    with patch.object(coordinator, "_refresh_token", AsyncMock(return_value="t")):
        data = await coordinator._async_update_data()
    assert "meal_plans" in data
    assert "shopping_lists" in data
    assert "pantry_items" in data


async def test_update_data_auth_failed_propagates(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """``ConfigEntryAuthFailed`` is re-raised so HA triggers re-auth."""
    coordinator, client = coordinator_pair
    client.async_get_meal_plans.side_effect = ConfigEntryAuthFailed("401")
    with (
        patch.object(coordinator, "_refresh_token", AsyncMock(return_value="t")),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._async_update_data()


async def test_update_data_api_error_becomes_update_failed(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """``CuliplanApiError`` on a critical slice raises ``UpdateFailed``."""
    coordinator, client = coordinator_pair
    client.async_get_meal_plans.side_effect = CuliplanApiError("boom")
    with (
        patch.object(coordinator, "_refresh_token", AsyncMock(return_value="t")),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


async def test_pantry_slice_failure_is_best_effort(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """A pantry failure does NOT abort the update."""
    coordinator, client = coordinator_pair
    client.async_get_pantry_items.side_effect = CuliplanApiError("no pantry")
    with patch.object(coordinator, "_refresh_token", AsyncMock(return_value="t")):
        data = await coordinator._async_update_data()
    assert data["pantry_items"] == []


async def test_handle_event_meal_plan_updated(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """A ``meal_plan.updated`` event refreshes meal plans."""
    coordinator, client = coordinator_pair
    coordinator.async_set_updated_data({"meal_plans": [], "shopping_lists": []})
    client.async_get_meal_plans.return_value = [{"id": "current", "slots": []}]
    await coordinator._handle_event({"type": "meal_plan.updated"})
    assert coordinator.data["meal_plans"] == [{"id": "current", "slots": []}]


async def test_handle_event_shopping_list(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """Shopping events refresh the shopping slice."""
    coordinator, client = coordinator_pair
    coordinator.async_set_updated_data({"shopping_lists": []})
    client.async_get_shopping_lists.return_value = [{"id": "default", "items": []}]
    await coordinator._handle_event({"type": "shopping_list.item.added"})
    assert coordinator.data["shopping_lists"] == [{"id": "default", "items": []}]


async def test_handle_event_pantry(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """Pantry events refresh the pantry slice."""
    coordinator, client = coordinator_pair
    coordinator.async_set_updated_data({"pantry_items": []})
    client.async_get_pantry_items.return_value = [{"id": "p1"}]
    await coordinator._handle_event({"type": "pantry.item.updated"})
    assert coordinator.data["pantry_items"] == [{"id": "p1"}]


async def test_handle_event_unknown_type_is_noop(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """An unknown event type is silently ignored."""
    coordinator, client = coordinator_pair
    coordinator.async_set_updated_data({"meal_plans": []})
    await coordinator._handle_event({"type": "weather.changed"})
    assert client.async_get_meal_plans.await_count == 0


async def test_refresh_helpers_swallow_api_errors(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """Per-slice helpers log & return on error rather than raising."""
    coordinator, client = coordinator_pair
    coordinator.async_set_updated_data(
        {"meal_plans": [], "shopping_lists": [], "pantry_items": []}
    )
    client.async_get_meal_plans.side_effect = CuliplanApiError("x")
    client.async_get_shopping_lists.side_effect = CuliplanApiError("x")
    client.async_get_pantry_items.side_effect = CuliplanApiError("x")
    await coordinator._refresh_meal_plans()
    await coordinator._refresh_shopping_lists()
    await coordinator._refresh_pantry()
    # State unchanged.
    assert coordinator.data["meal_plans"] == []


async def test_async_stop_when_never_started(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """``async_stop`` is safe even if the connection never opened."""
    coordinator, _ = coordinator_pair
    await coordinator.async_stop()
    assert coordinator._stopped is True


async def test_async_start_when_stopped_does_not_connect(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """``_connect`` returns early once ``async_stop`` has been called."""
    coordinator, _ = coordinator_pair
    coordinator._stopped = True
    with patch.object(
        coordinator, "_refresh_token", AsyncMock(return_value="t")
    ) as mock:
        await coordinator._connect()
    mock.assert_not_called()


async def test_schedule_reconnect_noop_when_stopped(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """``_schedule_reconnect`` is a no-op once stopped."""
    coordinator, _ = coordinator_pair
    coordinator._stopped = True
    coordinator._schedule_reconnect()
    assert coordinator._reconnect_task is None


async def test_connect_handles_connection_error(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """A Socket.IO ConnectionError schedules a reconnect rather than raising."""
    coordinator, _ = coordinator_pair
    with (
        patch.object(coordinator, "_refresh_token", AsyncMock(return_value="t")),
        patch(
            "homeassistant.components.culiplan.coordinator.socketio.AsyncClient"
        ) as cls,
    ):
        instance = cls.return_value
        instance.event = lambda *a, **k: lambda fn: fn
        instance.on = lambda *a, **k: lambda fn: fn
        instance.connect = AsyncMock(
            side_effect=socketio.exceptions.ConnectionError("nope")
        )
        instance.disconnect = AsyncMock()
        with patch.object(coordinator, "_schedule_reconnect") as sched:
            await coordinator._connect()
        sched.assert_called_once()
    await coordinator.async_stop()


async def test_schedule_reconnect_runs_loop_and_stops(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """The reconnect loop kicks off and is cancellable via async_stop."""
    coordinator, _ = coordinator_pair
    # Make the reconnect attempt finish quickly: pretend connection succeeds
    # immediately on first try.
    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch.object(coordinator, "_connect", new_callable=AsyncMock) as conn,
    ):

        async def _set_connected() -> None:
            coordinator._connected = True

        conn.side_effect = _set_connected
        coordinator._schedule_reconnect(delay=0)
        # Allow the background task to run.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
    await coordinator.async_stop()


async def test_reconnect_loop_swallows_errors(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """Reconnect attempts that raise are caught and the loop exits on stop."""
    coordinator, _ = coordinator_pair
    call_count = 0

    async def _failing_connect() -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            coordinator._stopped = True
        raise RuntimeError("fail")

    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch.object(coordinator, "_connect", side_effect=_failing_connect),
    ):
        coordinator._schedule_reconnect(delay=0)
        # Pump loop until task done.
        for _ in range(20):
            await asyncio.sleep(0)
            if (
                coordinator._reconnect_task is not None
                and coordinator._reconnect_task.done()
            ):
                break
    await coordinator.async_stop()


async def test_schedule_reconnect_skips_if_task_running(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """A second ``_schedule_reconnect`` while one is running is a no-op."""
    coordinator, _ = coordinator_pair

    async def _forever() -> None:
        await asyncio.Event().wait()

    coordinator._reconnect_task = hass.async_create_background_task(
        _forever(), name="t"
    )
    coordinator._schedule_reconnect(delay=0)
    # The original task is still the one in place.
    assert coordinator._reconnect_task is not None
    coordinator._reconnect_task.cancel()


async def test_reconnect_loop_applies_jitter(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """Two coordinators reconnecting with the same base delay get different sleeps.

    The jitter band is 0-25 % of the current base; with `random.uniform` seeded
    differently across calls, two consecutive sleep arguments must not be
    bit-identical. Guards against accidentally reverting to a fixed-delay loop.
    """
    coordinator, _ = coordinator_pair
    captured: list[float] = []

    async def _capturing_sleep(wait: float) -> None:
        captured.append(wait)
        # Flip the coordinator to "connected" after the first sleep so the
        # loop exits cleanly.
        if len(captured) >= 2:
            coordinator._connected = True

    async def _noop_connect() -> None:
        return

    with (
        patch("asyncio.sleep", new=_capturing_sleep),
        patch.object(coordinator, "_connect", new=_noop_connect),
    ):
        coordinator._schedule_reconnect(delay=4.0)
        for _ in range(20):
            await asyncio.sleep(0)
            if (
                coordinator._reconnect_task is not None
                and coordinator._reconnect_task.done()
            ):
                break

    await coordinator.async_stop()
    # First wait must be base + jitter ∈ [4.0, 5.0).
    assert 4.0 <= captured[0] < 5.0, f"first sleep out of band: {captured[0]}"
    # Second wait uses doubled base: ∈ [8.0, 10.0).
    assert 8.0 <= captured[1] < 10.0, f"second sleep out of band: {captured[1]}"
    # Statistically, the jitter fraction (uniform 0..0.25*base) on a 4s base
    # makes a 0.0-exact draw vanishingly unlikely. Guard against fixed delay.
    assert captured[0] != 4.0 or captured[1] != 8.0


async def test_reconnect_delay_caps_at_max(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """Backoff caps at 60s + 25% jitter (never grows unbounded)."""
    coordinator, _ = coordinator_pair
    captured: list[float] = []
    call_count = 0

    async def _capturing_sleep(wait: float) -> None:
        nonlocal call_count
        captured.append(wait)
        call_count += 1
        if call_count >= 10:
            coordinator._stopped = True

    async def _noop_connect() -> None:
        return

    with (
        patch("asyncio.sleep", new=_capturing_sleep),
        patch.object(coordinator, "_connect", new=_noop_connect),
    ):
        # Start at a high delay so we cap fast.
        coordinator._schedule_reconnect(delay=50.0)
        for _ in range(40):
            await asyncio.sleep(0)
            if (
                coordinator._reconnect_task is not None
                and coordinator._reconnect_task.done()
            ):
                break

    await coordinator.async_stop()
    # Once base hits the 60s cap, sleep is in [60, 75).
    for wait in captured[3:]:
        assert wait < 75.1, f"sleep {wait} exceeded cap + jitter"


async def test_refresh_token_propagates(
    hass: HomeAssistant,
    coordinator_pair: tuple[CuliplanCoordinator, MagicMock],
) -> None:
    """``_refresh_token`` updates the client and returns the token."""
    coordinator, client = coordinator_pair
    with (
        patch(
            "homeassistant.components.culiplan.coordinator"
            ".config_entry_oauth2_flow.async_get_config_entry_implementation",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.culiplan.coordinator"
            ".config_entry_oauth2_flow.OAuth2Session"
        ) as cls,
    ):
        cls.return_value.async_ensure_token_valid = AsyncMock()
        cls.return_value.token = {"access_token": "FRESH"}
        token = await coordinator._refresh_token()
    assert token == "FRESH"
    client.set_access_token.assert_called_with("FRESH")
