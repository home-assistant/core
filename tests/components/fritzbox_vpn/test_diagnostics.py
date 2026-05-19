"""Tests for diagnostics platform."""

import pytest

from homeassistant.components.fritzbox_vpn.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.fritzbox_vpn.models import FritzboxVpnRuntimeData
from homeassistant.core import HomeAssistant

from .fixtures import MOCK_VPN_CONNECTIONS

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_diagnostics_redacts_credentials(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Diagnostics never include passwords."""
    mock_config_entry.add_to_hass(hass)

    mock_coordinator = type(
        "C",
        (),
        {
            "last_update_success": True,
            "data": MOCK_VPN_CONNECTIONS,
        },
    )()
    mock_config_entry.runtime_data = FritzboxVpnRuntimeData(
        coordinator=mock_coordinator
    )

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert result["host"] == mock_config_entry.data["host"]
    assert result["vpn_connection_count"] == 2
    entry_data = result["entry"].get("data", {})
    assert entry_data.get("password") != mock_config_entry.data["password"]


@pytest.mark.asyncio
async def test_diagnostics_skips_non_dict_connections(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Diagnostics ignores malformed coordinator entries."""
    mock_config_entry.add_to_hass(hass)
    mock_coordinator = type(
        "C",
        (),
        {"last_update_success": True, "data": {"bad": "value"}},
    )()
    mock_config_entry.runtime_data = FritzboxVpnRuntimeData(
        coordinator=mock_coordinator
    )
    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert result["vpn_connection_count"] == 0
    assert result["vpn_connections"] == []


@pytest.mark.asyncio
async def test_diagnostics_without_loaded_coordinator(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Diagnostics works when integration data is not loaded."""
    mock_config_entry.add_to_hass(hass)
    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert result["vpn_connection_count"] == 0
