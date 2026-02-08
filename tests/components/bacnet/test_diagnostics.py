"""Tests for the BACnet diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.bacnet.const import (
    CONF_ENTRY_TYPE,
    CONF_INTERFACE,
    ENTRY_TYPE_DEVICE,
    ENTRY_TYPE_HUB,
)
from homeassistant.core import HomeAssistant

from . import init_integration_with_hub

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_hub_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bacnet_client: AsyncMock,
) -> None:
    """Test diagnostics for a hub config entry."""
    hub_entry, _ = await init_integration_with_hub(hass)

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, hub_entry)

    assert "entry_data" in diagnostics
    assert diagnostics["entry_data"][CONF_ENTRY_TYPE] == ENTRY_TYPE_HUB
    assert diagnostics["entry_data"][CONF_INTERFACE] == "eth0"
    assert "client_connected" in diagnostics
    assert "hub_device_id" in diagnostics


async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bacnet_client: AsyncMock,
) -> None:
    """Test diagnostics for a device config entry."""
    _, device_entry = await init_integration_with_hub(hass)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, device_entry
    )

    assert "entry_data" in diagnostics
    assert diagnostics["entry_data"][CONF_ENTRY_TYPE] == ENTRY_TYPE_DEVICE
    assert "entry_options" in diagnostics
    assert "device_info" in diagnostics
    assert diagnostics["device_info"]["device_id"] == 1234
    assert diagnostics["device_info"]["name"] == "Test HVAC Controller"
    assert "initial_setup_done" in diagnostics
    assert "cov_subscriptions" in diagnostics
    assert "objects" in diagnostics
    assert "values" in diagnostics
