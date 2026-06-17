"""Tests for the Karakeep sensor platform."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

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
            f"{mock_config_entry.entry_id}_{entity_id.removeprefix('sensor.karakeep_')}"
        )


async def test_device_info(
    hass: HomeAssistant,
    mock_karakeep_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry entry."""
    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={("karakeep", mock_config_entry.entry_id)}
    )
    assert device_entry is not None
    assert device_entry.name == "Karakeep"
    assert device_entry.manufacturer == "Karakeep"
