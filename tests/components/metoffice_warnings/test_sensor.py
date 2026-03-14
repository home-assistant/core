"""Tests for Met Office Weather Warnings sensor."""

from datetime import UTC, datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensor_with_warnings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_warnings_response: AiohttpClientMocker,
) -> None:
    """Test sensor state with warnings present."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.south_west_england_weather_warnings")
    assert state is not None
    assert state.state == datetime(2026, 3, 12, 8, 0, tzinfo=UTC).isoformat()

    attrs = state.attributes
    assert "warnings" in attrs
    assert len(attrs["warnings"]) == 1
    assert attrs["warnings"][0]["level"] == "Yellow"
    assert attrs["warnings"][0]["warning_type"] == "Rain"


async def test_sensor_with_multiple_warnings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_multiple_warnings_response: AiohttpClientMocker,
) -> None:
    """Test sensor state with multiple warnings."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.south_west_england_weather_warnings")
    assert state is not None

    attrs = state.attributes
    assert "warnings" in attrs
    assert len(attrs["warnings"]) == 3


async def test_sensor_no_warnings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_no_warnings_response: AiohttpClientMocker,
) -> None:
    """Test sensor state with no warnings."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.south_west_england_weather_warnings")
    assert state is not None
    assert state.state == datetime(2026, 3, 12, 8, 0, tzinfo=UTC).isoformat()

    # No warnings attribute when empty
    assert state.attributes.get("warnings") is None


async def test_sensor_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_warnings_response: AiohttpClientMocker,
) -> None:
    """Test sensor device info."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("sensor.south_west_england_weather_warnings")
    assert entry is not None
    assert entry.unique_id == f"{mock_config_entry.entry_id}_warnings"
