"""Tests for Fritz!Box VPN switch entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.fritzbox_vpn.const import STATUS_ENABLED
from homeassistant.components.fritzbox_vpn.switch import FritzBoxVPNSwitch
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .fixtures import MOCK_VPN_CONNECTIONS

from tests.common import MockConfigEntry


def _mock_coordinator() -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = MOCK_VPN_CONNECTIONS
    coordinator.last_update_success = True
    coordinator.get_vpn_status = MagicMock(return_value=STATUS_ENABLED)
    coordinator.toggle_vpn = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_switch_turn_on(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Switch turn_on calls coordinator toggle."""
    coordinator = _mock_coordinator()
    conn = MOCK_VPN_CONNECTIONS["conn-abc"]
    entity = FritzBoxVPNSwitch(coordinator, mock_config_entry, "conn-abc", conn)
    await entity.async_turn_on()
    coordinator.toggle_vpn.assert_awaited_once_with("conn-abc", True)


@pytest.mark.asyncio
async def test_switch_turn_on_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Switch turn_on raises HomeAssistantError when toggle fails."""
    coordinator = _mock_coordinator()
    coordinator.toggle_vpn = AsyncMock(return_value=False)
    entity = FritzBoxVPNSwitch(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_on()


def test_switch_available_and_state(mock_config_entry: MockConfigEntry) -> None:
    """Switch reflects coordinator VPN active state."""
    coordinator = _mock_coordinator()
    entity = FritzBoxVPNSwitch(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    assert entity.available
    assert entity.is_on
    assert entity.translation_key == "vpn"
