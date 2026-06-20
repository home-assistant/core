"""Tests for the Habitron system_health info."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.habitron.system_health import system_health_info
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def _mock_integration_version() -> None:
    """Stand in for HA's loader so ``system_health_info`` finds a version.

    ``system_health_info`` resolves the version via ``async_get_integration``;
    patch it so the tests do not depend on the integration being loaded.
    """
    with patch(
        "homeassistant.components.habitron.system_health.async_get_integration",
        new=AsyncMock(return_value=MagicMock(version="2.6.3")),
    ):
        yield


def _make_hub_entry(modules: int, sys_ok: bool) -> MagicMock:
    """Build a stub config entry with ``runtime_data`` pointing at a hub stub.

    Avoids using ``MockConfigEntry`` + a real loaded state to keep the
    test isolated from HA's config_entries teardown machinery, which
    hangs the event loop with a half-mocked SmartHub.
    """
    hub = MagicMock()
    hub.router.sys_ok = sys_ok
    hub.router.modules = [MagicMock() for _ in range(modules)]
    entry = MagicMock()
    entry.runtime_data = hub
    return entry


async def test_no_hubs(hass: HomeAssistant) -> None:
    """No loaded hubs reports ``no hubs`` and zero counts."""
    info = await system_health_info(hass)
    assert info == {
        "hbtn_version": "2.6.3",
        "hub_count": 0,
        "router_status": "no hubs",
        "module_count": 0,
    }


async def test_single_healthy_hub(hass: HomeAssistant) -> None:
    """A single hub reporting ``_sys_ok=True`` is shown as 'ok'."""
    entry = _make_hub_entry(modules=3, sys_ok=True)
    hass.config_entries.async_loaded_entries = MagicMock(return_value=[entry])
    info = await system_health_info(hass)
    assert info == {
        "hbtn_version": "2.6.3",
        "hub_count": 1,
        "router_status": "ok",
        "module_count": 3,
    }


async def test_aggregates_module_counts_across_hubs(hass: HomeAssistant) -> None:
    """Module count is summed across all configured hubs."""
    entries = [
        _make_hub_entry(modules=2, sys_ok=True),
        _make_hub_entry(modules=1, sys_ok=True),
    ]
    hass.config_entries.async_loaded_entries = MagicMock(return_value=entries)
    info = await system_health_info(hass)
    assert info["hub_count"] == 2
    assert info["module_count"] == 3
    assert info["router_status"] == "ok"


async def test_status_errors_when_any_hub_fails(hass: HomeAssistant) -> None:
    """Router status flips to 'errors' as soon as any hub reports a problem."""
    entries = [
        _make_hub_entry(modules=0, sys_ok=True),
        _make_hub_entry(modules=0, sys_ok=False),
    ]
    hass.config_entries.async_loaded_entries = MagicMock(return_value=entries)
    info = await system_health_info(hass)
    assert info["router_status"] == "errors"
