"""Tests for the shared Telldus Live entity behavior."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.tellduslive.const import (
    BATTERY_LOW,
    BATTERY_OK,
    BATTERY_UNKNOWN,
)
from homeassistant.const import ATTR_BATTERY_LEVEL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .conftest import DEVICE_ID

SWITCH = "switch.kitchen"


@pytest.fixture
def device(mock_tellduslive: MagicMock, battery: int | None) -> MagicMock:
    """Return a mocked device reporting a battery level."""
    device = mock_tellduslive.devices[0]
    device.battery = battery
    device.lastUpdated = 1700000000
    return device


@pytest.mark.parametrize(
    ("battery", "expected"),
    [
        pytest.param(BATTERY_OK, 100, id="ok"),
        pytest.param(BATTERY_LOW, 1, id="low"),
        pytest.param(42, 42, id="percentage"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_battery_level(hass: HomeAssistant, expected: int) -> None:
    """Test the battery level attribute."""
    assert hass.states.get(SWITCH).attributes[ATTR_BATTERY_LEVEL] == expected


@pytest.mark.parametrize("battery", [BATTERY_UNKNOWN, None])
@pytest.mark.usefixtures("setup_integration")
async def test_battery_level_missing(hass: HomeAssistant) -> None:
    """Test no battery attribute is reported when the level is unknown."""
    assert ATTR_BATTERY_LEVEL not in hass.states.get(SWITCH).attributes


@pytest.mark.parametrize("battery", [None])
@pytest.mark.usefixtures("setup_integration")
async def test_last_updated_is_utc_iso(hass: HomeAssistant) -> None:
    """Test the last updated attribute is a timezone-aware timestamp."""
    assert (
        hass.states.get(SWITCH).attributes["time_last_updated"]
        == "2023-11-14T22:13:20+00:00"
    )


@pytest.mark.parametrize("battery", [None])
@pytest.mark.usefixtures("setup_integration")
async def test_device_info(
    device_registry: dr.DeviceRegistry, mock_config_entry: MockConfigEntry
) -> None:
    """Test the device registry entry built from the stored device info."""
    entry = device_registry.async_get_device_by_identifier(
        ("tellduslive", DEVICE_ID), mock_config_entry.entry_id
    )

    assert entry.name == "Kitchen"
    assert entry.model == "Selflearning-Switch"
    assert entry.manufacturer == "Arctech"


@pytest.mark.parametrize("battery", [None])
@pytest.mark.usefixtures("setup_integration")
async def test_unavailable_when_device_disappears(
    hass: HomeAssistant, mock_tellduslive: MagicMock
) -> None:
    """Test entities become unavailable when the account no longer lists them."""
    mock_tellduslive.device_ids = []
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH).state == STATE_UNAVAILABLE
