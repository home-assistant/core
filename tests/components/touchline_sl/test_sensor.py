"""Tests for the Roth Touchline SL sensor platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import make_mock_module, make_mock_zone

from tests.common import MockConfigEntry

BATTERY_ENTITY_ID = "sensor.zone_1_battery"


async def test_battery_sensor_with_battery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchlinesl_client: MagicMock,
) -> None:
    """Test that the battery sensor reports the correct level."""
    zone = make_mock_zone()
    zone.battery_level = 85
    module = make_mock_module([zone])
    mock_touchlinesl_client.modules = AsyncMock(return_value=[module])

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(BATTERY_ENTITY_ID)
    assert state is not None
    assert state.state == "85"


async def test_battery_sensor_no_battery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchlinesl_client: MagicMock,
) -> None:
    """Test that no battery sensor is created for wired zones without a battery."""
    zone = make_mock_zone()
    zone.battery_level = None
    module = make_mock_module([zone])
    mock_touchlinesl_client.modules = AsyncMock(return_value=[module])

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID) is None


async def test_battery_sensor_only_created_for_zones_with_battery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchlinesl_client: MagicMock,
) -> None:
    """Test that battery sensors are only created for wireless zones."""
    wired_zone = make_mock_zone(zone_id=1, name="Wired Zone")
    wired_zone.battery_level = None
    wireless_zone = make_mock_zone(zone_id=2, name="Wireless Zone")
    wireless_zone.battery_level = 75

    module = make_mock_module([wired_zone, wireless_zone])
    mock_touchlinesl_client.modules = AsyncMock(return_value=[module])

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wired_zone_battery") is None
    assert hass.states.get("sensor.wireless_zone_battery") is not None


@pytest.mark.parametrize("alarm", ["no_communication", "sensor_damaged"])
async def test_battery_sensor_unavailable_on_alarm(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchlinesl_client: MagicMock,
    alarm: str,
) -> None:
    """Test that the battery sensor is unavailable when the zone has an alarm."""
    zone = make_mock_zone(alarm=alarm)
    zone.battery_level = 50
    module = make_mock_module([zone])
    mock_touchlinesl_client.modules = AsyncMock(return_value=[module])

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(BATTERY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
