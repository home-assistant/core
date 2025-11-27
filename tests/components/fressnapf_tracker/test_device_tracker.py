"""Test the Fressnapf Tracker device tracker platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.fressnapf_tracker.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_SERIAL_NUMBER

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
@pytest.mark.usefixtures("mock_config_entry")
async def test_device_tracker_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device tracker entity is created correctly."""
    entity_id = "device_tracker.fluffy"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["latitude"] == 52.520008
    assert state.attributes["longitude"] == 13.404954
    assert state.attributes["gps_accuracy"] == 10
    assert state.attributes["source_type"] == SourceType.GPS

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.unique_id == MOCK_SERIAL_NUMBER

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_SERIAL_NUMBER)}
    )
    assert device_entry is not None
    assert device_entry.name == "Fluffy"
    assert device_entry.manufacturer == "Fressnapf"
    assert device_entry.model == "GPS Tracker 2.0"


async def test_device_tracker_no_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tracker_no_position,
) -> None:
    """Test device tracker is unavailable when position is None."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fressnapf_tracker.coordinator.ApiClient"
    ) as mock_api:
        client = mock_api.return_value
        client.get_tracker = AsyncMock(return_value=mock_tracker_no_position)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "device_tracker.fluffy"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "latitude" not in state.attributes
    assert "longitude" not in state.attributes
    assert "gps_accuracy" not in state.attributes
