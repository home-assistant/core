"""Tests for the Seko Pooldose switches."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.pooldose.switch import PooldoseSwitch


@pytest.fixture
def mock_coordinator():
    """Fixture for a mocked coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "devicedata": {
            "PDPR1H1HAW100_FW539187": {
                "relay_1": True,
            }
        }
    }
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_api():
    """Fixture for a mocked API."""
    api = MagicMock()
    api.serial_key = "PDPR1H1HAW100_FW539187"
    api.set_relay = AsyncMock()
    api.set_value = AsyncMock()
    return api


@pytest.mark.asyncio
async def test_switch_is_on_and_turns_off(mock_coordinator, mock_api) -> None:
    """Test switch is on and can be turned off."""
    switch = PooldoseSwitch(
        mock_coordinator,
        mock_api,
        "Relay 1",
        "relay_1",
        "relay_1",
        False,  # off_val
        True,  # on_val
        "PDPR1H1HAW100_FW539187",  # serialnumber
        None,  # entity_category
        None,  # device_class
        {},  # device_info_dict
        True,  # enabled_by_default
    )
    assert switch.is_on is True

    await switch.async_turn_off()
    mock_api.set_value.assert_awaited_with("relay_1", False, "STRING")


@pytest.mark.asyncio
async def test_switch_is_off_and_turns_on(mock_coordinator, mock_api) -> None:
    """Test switch is off and can be turned on."""
    mock_coordinator.data["devicedata"]["PDPR1H1HAW100_FW539187"]["relay_1"] = False
    switch = PooldoseSwitch(
        mock_coordinator,
        mock_api,
        "Relay 1",
        "relay_1",
        "relay_1",
        False,  # off_val
        True,  # on_val
        "PDPR1H1HAW100_FW539187",
        None,
        None,
        {},
        True,
    )
    assert switch.is_on is False

    await switch.async_turn_on()
    mock_api.set_value.assert_awaited_with("relay_1", True, "STRING")


def test_switch_is_on_returns_none_on_missing_key(mock_coordinator, mock_api) -> None:
    """Test switch returns None if key is missing."""
    switch = PooldoseSwitch(
        mock_coordinator,
        mock_api,
        "Relay 1",
        "relay_1",
        "invalid_key",
        False,
        True,
        "PDPR1H1HAW100_FW539187",
        None,
        None,
        {},
        True,
    )
    assert switch.is_on is None
