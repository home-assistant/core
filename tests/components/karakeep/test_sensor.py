"""Tests for the Karakeep sensor platform."""

from unittest.mock import AsyncMock

from homeassistant.const import CONF_URL, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .const import TEST_STATS, TEST_URL

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_karakeep_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Karakeep sensors."""
    await setup_integration(hass, mock_config_entry)

    expected_states = {
        "sensor.karakeep_archived": "3",
        "sensor.karakeep_bookmarks": "10",
        "sensor.karakeep_favorites": "2",
        "sensor.karakeep_highlights": "4",
        "sensor.karakeep_lists": "5",
        "sensor.karakeep_tags": "6",
    }

    for entity_id, state in expected_states.items():
        assert hass.states.get(entity_id).state == state
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == (
            f"{mock_config_entry.data[CONF_URL]}_{entity_id.removeprefix('sensor.karakeep_')}"
        )


async def test_sensor_ignores_non_integer_values(
    hass: HomeAssistant,
    mock_karakeep_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test non-integer stat values render as unknown."""
    mock_karakeep_client.async_get_stats.return_value = {
        **TEST_STATS,
        "numBookmarks": "10",
    }

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.karakeep_bookmarks").state == STATE_UNKNOWN


async def test_device_info(
    hass: HomeAssistant,
    mock_karakeep_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry entry."""
    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={("karakeep", TEST_URL)}
    )
    assert device_entry is not None
    assert device_entry.name == "Karakeep"
    assert device_entry.manufacturer == "Karakeep"
