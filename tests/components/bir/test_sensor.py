"""Tests for the BIR sensors."""

import pytest

from homeassistant.components.bir.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_PROPERTY_ID

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
    assert len(entity_entries) == 4


@pytest.mark.parametrize(
    ("entity_id", "expected_date"),
    [
        ("sensor.testveien_1_bergen_mixed_waste_pickup", "2026-04-15"),
        ("sensor.testveien_1_bergen_paper_and_plastic_pickup", "2026-04-20"),
        ("sensor.testveien_1_bergen_food_waste_pickup", "2026-04-10"),
        (
            "sensor.testveien_1_bergen_glass_and_metal_packaging_pickup",
            "2026-05-01",
        ),
    ],
)
async def test_sensor_states(
    hass: HomeAssistant,
    entity_id: str,
    expected_date: str,
) -> None:
    """Test the BIR waste pickup sensor states."""
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
