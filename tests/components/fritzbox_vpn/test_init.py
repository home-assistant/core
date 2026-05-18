"""Tests for integration setup and unload."""

from unittest.mock import AsyncMock, patch

import pytest
from custom_components.fritzbox_vpn import (
    PLATFORMS,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.fritzbox_vpn.models import FritzboxVpnRuntimeData
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_VPN_CONNECTIONS


@pytest.mark.asyncio
async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Setup creates coordinator and forwards platforms."""
    mock_config_entry.add_to_hass(hass)

    mock_coordinator = AsyncMock()
    mock_coordinator.data = MOCK_VPN_CONNECTIONS
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.fritz_session = AsyncMock()
    mock_coordinator.fritz_session.async_close = AsyncMock()

    forward_mock = AsyncMock(return_value=True)
    with (
        patch(
            "custom_components.fritzbox_vpn.FritzBoxVPNCoordinator",
            return_value=mock_coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            forward_mock,
        ),
    ):
        assert await async_setup_entry(hass, mock_config_entry)

    assert isinstance(mock_config_entry.runtime_data, FritzboxVpnRuntimeData)
    assert mock_config_entry.runtime_data.coordinator is mock_coordinator
    forward_mock.assert_awaited_once_with(mock_config_entry, PLATFORMS)


@pytest.mark.asyncio
async def test_setup_entry_auth_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Setup raises ConfigEntryAuthFailed on authentication errors."""
    mock_config_entry.add_to_hass(hass)

    mock_coordinator = AsyncMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=ValueError("Login failed: Invalid SID")
    )

    with patch(
        "custom_components.fritzbox_vpn.FritzBoxVPNCoordinator",
        return_value=mock_coordinator,
    ):
        with pytest.raises(ConfigEntryAuthFailed):
            await async_setup_entry(hass, mock_config_entry)


@pytest.mark.asyncio
async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Unload removes coordinator and closes session."""
    mock_config_entry.add_to_hass(hass)
    mock_coordinator = AsyncMock()
    mock_coordinator.fritz_session = AsyncMock()
    mock_coordinator.fritz_session.async_close = AsyncMock()
    mock_config_entry.runtime_data = FritzboxVpnRuntimeData(coordinator=mock_coordinator)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=True),
    ):
        assert await async_unload_entry(hass, mock_config_entry)

    assert mock_config_entry.runtime_data is None
    mock_coordinator.fritz_session.async_close.assert_awaited_once()
