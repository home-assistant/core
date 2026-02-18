"""Tests for the Roth Touchline SL climate platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_ID = "climate.zone_1"


def make_mock_zone(
    zone_id: int = 1, name: str = "Zone 1", alarm: str | None = None
) -> MagicMock:
    """Return a mock Zone with configurable alarm state."""
    zone = MagicMock()
    zone.id = zone_id
    zone.name = name
    zone.temperature = 21.5
    zone.target_temperature = 22.0
    zone.humidity = 45
    zone.mode = "constantTemp"
    zone.algorithm = "heating"
    zone.relay_on = False
    zone.alarm = alarm
    zone.schedule = None
    zone.enabled = True
    zone.signal_strength = 100
    zone.battery_level = None
    return zone


def make_mock_module(zones: list) -> MagicMock:
    """Return a mock module with the given zones."""
    module = MagicMock()
    module.id = "deadbeef"
    module.name = "Foobar"
    module.type = "SL"
    module.version = "1.0"
    module.zones = AsyncMock(return_value=zones)
    module.schedules = AsyncMock(return_value=[])
    return module


@pytest.fixture
def mock_touchlinesl_full_client(
    mock_config_entry: MockConfigEntry,
) -> Generator[MagicMock]:
    """Mock a pytouchlinesl client with full module/zone support."""
    with patch(
        "homeassistant.components.touchline_sl.TouchlineSL",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.user_id = AsyncMock(return_value=12345)
        yield client


async def test_climate_zone_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchlinesl_full_client: MagicMock,
) -> None:
    """Test that the climate entity is available when zone has no alarm."""
    zone = make_mock_zone(alarm=None)
    module = make_mock_module([zone])
    mock_touchlinesl_full_client.modules = AsyncMock(return_value=[module])

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_climate_zone_unavailable_on_no_communication(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchlinesl_full_client: MagicMock,
) -> None:
    """Test that the climate entity is unavailable when zone reports noCommunication."""
    zone = make_mock_zone(alarm="no_communication")
    module = make_mock_module([zone])
    mock_touchlinesl_full_client.modules = AsyncMock(return_value=[module])

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_climate_zone_unavailable_on_sensor_damaged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchlinesl_full_client: MagicMock,
) -> None:
    """Test that the climate entity is unavailable when zone reports sensorDamaged."""
    zone = make_mock_zone(alarm="sensor_damaged")
    module = make_mock_module([zone])
    mock_touchlinesl_full_client.modules = AsyncMock(return_value=[module])

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
