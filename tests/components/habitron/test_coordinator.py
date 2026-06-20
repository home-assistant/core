"""Tests for the Habitron coordinator."""

from unittest.mock import AsyncMock, MagicMock

from habitron_client import HabitronConnectionError, HabitronTimeoutError
import pytest

from homeassistant.components.habitron.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.habitron.coordinator import HbtnCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed


def _make_comm(hass: HomeAssistant) -> MagicMock:
    """Build a stub for ``HbtnComm`` carrying just what the coordinator reads."""
    comm = MagicMock()
    comm._config = MagicMock()
    comm.update_suspended = False
    comm.async_system_update = AsyncMock(return_value=b"compact-status")
    return comm


async def test_coordinator_normal_update(hass: HomeAssistant) -> None:
    """``_async_update_data`` returns the compact status and forwards to comm."""
    comm = _make_comm(hass)
    coord = HbtnCoordinator(hass, MagicMock(), comm)
    result = await coord._async_update_data()
    assert result == b"compact-status"
    comm.async_system_update.assert_awaited_once()


async def test_coordinator_router_system_error_repair_issue(
    hass: HomeAssistant,
) -> None:
    """A router system error raises a repair issue, cleared on recovery."""
    comm = _make_comm(hass)
    comm.router = MagicMock(uid="rt_1", sys_ok=False)
    coord = HbtnCoordinator(hass, MagicMock(), comm)
    registry = ir.async_get(hass)

    await coord._async_update_data()
    assert registry.async_get_issue(DOMAIN, "router_system_error_rt_1") is not None

    comm.router.sys_ok = True
    await coord._async_update_data()
    assert registry.async_get_issue(DOMAIN, "router_system_error_rt_1") is None


async def test_coordinator_timeout_raises_update_failed(
    hass: HomeAssistant,
) -> None:
    """A timeout in ``async_system_update`` is wrapped in ``UpdateFailed``."""
    comm = _make_comm(hass)
    comm.async_system_update.side_effect = TimeoutError("hub silent")
    coord = HbtnCoordinator(hass, MagicMock(), comm)
    with pytest.raises(UpdateFailed) as exc_info:
        await coord._async_update_data()
    assert exc_info.value.translation_key == "update_timeout"


async def test_coordinator_change_detection(hass: HomeAssistant) -> None:
    """``always_update`` is False so the heartbeat only fans out on changes."""
    comm = _make_comm(hass)
    coord = HbtnCoordinator(hass, MagicMock(), comm)
    assert coord.always_update is False


async def test_coordinator_uses_fixed_scan_interval(hass: HomeAssistant) -> None:
    """The coordinator's interval is the integration's hard-coded SCAN_INTERVAL."""
    comm = _make_comm(hass)
    coord = HbtnCoordinator(hass, MagicMock(), comm)
    assert coord.update_interval == SCAN_INTERVAL


async def test_async_setup_runs_first_refresh(hass: HomeAssistant) -> None:
    """``_async_setup`` delegates to ``_async_update_data``."""
    comm = _make_comm(hass)
    coord = HbtnCoordinator(hass, MagicMock(), comm)
    await coord._async_setup()
    comm.async_system_update.assert_awaited()


async def test_coordinator_network_error_raises_update_failed(
    hass: HomeAssistant,
) -> None:
    """An OSError in ``async_system_update`` is wrapped in ``UpdateFailed``."""
    comm = _make_comm(hass)
    comm.async_system_update.side_effect = OSError("dns down")
    coord = HbtnCoordinator(hass, MagicMock(), comm)
    with pytest.raises(UpdateFailed) as exc_info:
        await coord._async_update_data()
    assert exc_info.value.translation_key == "update_network_error"


async def test_coordinator_library_timeout_raises_update_failed(
    hass: HomeAssistant,
) -> None:
    """A HabitronTimeoutError from the client maps to ``update_timeout``."""
    comm = _make_comm(hass)
    comm.async_system_update.side_effect = HabitronTimeoutError("no response")
    coord = HbtnCoordinator(hass, MagicMock(), comm)
    with pytest.raises(UpdateFailed) as exc_info:
        await coord._async_update_data()
    assert exc_info.value.translation_key == "update_timeout"


async def test_coordinator_library_error_raises_update_failed(
    hass: HomeAssistant,
) -> None:
    """Any other HabitronError maps to ``update_network_error``."""
    comm = _make_comm(hass)
    comm.async_system_update.side_effect = HabitronConnectionError("bus down")
    coord = HbtnCoordinator(hass, MagicMock(), comm)
    with pytest.raises(UpdateFailed) as exc_info:
        await coord._async_update_data()
    assert exc_info.value.translation_key == "update_network_error"
