"""Tests for the BACnet diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.bacnet.const import CONF_INTERFACE
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_hub_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bacnet_client: AsyncMock,
) -> None:
    """Test diagnostics for a hub config entry with devices."""
    entry = await init_integration(hass)

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert "entry_data" in diagnostics
    assert diagnostics["entry_data"][CONF_INTERFACE] == "eth0"
    assert "client_connected" in diagnostics
    assert "devices" in diagnostics
    assert len(diagnostics["devices"]) > 0

    # Check that device diagnostics are included
    device_diag = next(iter(diagnostics["devices"].values()))
    assert "device_info" in device_diag
    assert device_diag["device_info"]["device_id"] == 1234
    assert device_diag["device_info"]["name"] == "Test HVAC Controller"
    assert "initial_setup_done" in device_diag
    assert "cov_subscriptions" in device_diag
    assert "objects" in device_diag
    assert "values" in device_diag
