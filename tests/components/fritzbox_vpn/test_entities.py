"""Tests for entity platforms (switch, sensor, binary_sensor)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.fritzbox_vpn.binary_sensor import (
    FritzBoxVPNConnectedBinarySensor,
)
from custom_components.fritzbox_vpn.const import STATUS_ENABLED
from custom_components.fritzbox_vpn.sensor import (
    FritzBoxVPNStatusSensor,
    FritzBoxVPNUIDSensor,
    FritzBoxVPNVPNUIDSensor,
)
from custom_components.fritzbox_vpn.switch import FritzBoxVPNSwitch
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_VPN_CONNECTIONS


def _mock_coordinator() -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = MOCK_VPN_CONNECTIONS
    coordinator.last_update_success = True
    coordinator.get_vpn_status = MagicMock(return_value=STATUS_ENABLED)
    coordinator.toggle_vpn = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_switch_turn_on(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Switch turn_on calls coordinator toggle."""
    coordinator = _mock_coordinator()
    conn = MOCK_VPN_CONNECTIONS["conn-abc"]
    entity = FritzBoxVPNSwitch(coordinator, mock_config_entry, "conn-abc", conn)
    await entity.async_turn_on()
    coordinator.toggle_vpn.assert_awaited_once_with("conn-abc", True)


@pytest.mark.asyncio
async def test_switch_turn_on_failure(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Switch turn_on raises HomeAssistantError when toggle fails."""
    coordinator = _mock_coordinator()
    coordinator.toggle_vpn = AsyncMock(return_value=False)
    entity = FritzBoxVPNSwitch(coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"])
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


def test_binary_sensor_connected(mock_config_entry: MockConfigEntry) -> None:
    """Binary sensor is off when VPN is not connected."""
    coordinator = _mock_coordinator()
    entity = FritzBoxVPNConnectedBinarySensor(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    assert entity.available
    assert entity.is_on is False
    assert entity.translation_key == "connected"


def test_status_sensor_enum(mock_config_entry: MockConfigEntry) -> None:
    """Status sensor exposes enum options and value."""
    coordinator = _mock_coordinator()
    entity = FritzBoxVPNStatusSensor(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    assert entity.native_value == STATUS_ENABLED
    assert entity.options is not None
    assert entity.translation_key == "status"


def test_uid_sensors(mock_config_entry: MockConfigEntry) -> None:
    """UID sensors expose connection identifiers."""
    coordinator = _mock_coordinator()
    uid_sensor = FritzBoxVPNUIDSensor(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    vpn_uid_sensor = FritzBoxVPNVPNUIDSensor(
        coordinator, mock_config_entry, "conn-abc", MOCK_VPN_CONNECTIONS["conn-abc"]
    )
    assert uid_sensor.native_value == "conn-abc"
    assert vpn_uid_sensor.native_value == "wg-1"
