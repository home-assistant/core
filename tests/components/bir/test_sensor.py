"""Tests for the BIR sensors."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.bir.const import DOMAIN
from homeassistant.components.bir.sensor import SENSORS
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_PROPERTY_ID, MOCK_REFERENCE_DATE

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_sensors_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that all BIR sensors are created."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    # 4 days_until (enabled) + 4 date (disabled)
    assert len(entity_entries) == len(SENSORS)


@pytest.mark.parametrize(
    ("entity_id", "expected_value"),
    [
        ("sensor.teststreet_1_bergen_mixed_waste_days_until_pickup", "13"),
        ("sensor.teststreet_1_bergen_paper_and_plastic_days_until_pickup", "18"),
        ("sensor.teststreet_1_bergen_food_waste_days_until_pickup", "8"),
        (
            "sensor.teststreet_1_bergen_glass_and_metal_packaging_days_until_pickup",
            "29",
        ),
    ],
)
async def test_days_until_sensor_states(
    hass: HomeAssistant,
    entity_id: str,
    expected_value: str,
) -> None:
    """Test the BIR days until pickup sensor states."""
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_value


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "expected_date"),
    [
        ("sensor.teststreet_1_bergen_mixed_waste_pickup", "2026-04-15"),
        ("sensor.teststreet_1_bergen_paper_and_plastic_pickup", "2026-04-20"),
        ("sensor.teststreet_1_bergen_food_waste_pickup", "2026-04-10"),
        (
            "sensor.teststreet_1_bergen_glass_and_metal_packaging_pickup",
            "2026-05-01",
        ),
    ],
)
async def test_date_sensor_states(
    hass: HomeAssistant,
    entity_id: str,
    expected_date: str,
) -> None:
    """Test the BIR date pickup sensor states."""
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_date


async def test_sensor_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors are assigned to the correct device."""
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_PROPERTY_ID)}
    )
    assert device_entry is not None
    assert device_entry.manufacturer == "BIR"

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


async def test_sensor_unavailable_when_waste_type_missing(
    hass: HomeAssistant,
    mock_bir_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor becomes unavailable when waste type disappears from data."""
    mock_bir_client.get_pickups.return_value = []
    with patch(
        "homeassistant.components.bir.coordinator.dt_util.now",
        return_value=datetime.combine(MOCK_REFERENCE_DATE, datetime.min.time()),
    ):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.teststreet_1_bergen_mixed_waste_days_until_pickup")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
