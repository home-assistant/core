"""Tests for camera_list.py's fetch_camera_list."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.bosch_shc_camera.camera_list import fetch_camera_list
from homeassistant.helpers.update_coordinator import UpdateFailed


def _resp_cm(status: int) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.text = AsyncMock(return_value="")
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.asyncio
async def test_non_200_response_routes_outage_ping_through_spawn_tracked() -> None:
    """A non-200 response must schedule its outage ping via spawn_tracked.

    Not a bare `hass.async_create_task` — otherwise it can survive
    config-entry unload and keep running against a torn-down coordinator,
    bypassing the teardown contract the other outage-ping call sites
    already honor (Copilot review round 11).
    """

    def _spawn_tracked_close(coro, **_kwargs):
        coro.close()  # never actually scheduled here, avoid a leaked-coroutine warning
        return MagicMock()

    coordinator = SimpleNamespace(
        async_outage_ping_all=AsyncMock(),
        spawn_tracked=MagicMock(side_effect=_spawn_tracked_close),
    )
    session = MagicMock()
    session.get = MagicMock(return_value=_resp_cm(503))

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.camera_list.CLOUD_API",
            "https://example.boschsecurity.com",
        ),
        pytest.raises(UpdateFailed),
    ):
        await fetch_camera_list(coordinator, session, {}, "tok")

    coordinator.async_outage_ping_all.assert_called_once()
    coordinator.spawn_tracked.assert_called_once()
    _, call_kwargs = coordinator.spawn_tracked.call_args
    assert call_kwargs["name"] == "bosch_shc_camera_camera_list_outage_ping"
