"""Tests for WATERCryst entities."""

from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.watercryst.entity import WatercrystEntity

from tests.common import MockConfigEntry


def test_entity_initialization(config_entry: MockConfigEntry) -> None:
    """Test shared WATERCryst entity attributes."""
    coordinator = MagicMock()
    description = SensorEntityDescription(key="pressure")

    entity = WatercrystEntity(
        config_entry=config_entry,
        coordinator=coordinator,
        entity_description=description,
    )

    assert entity.unique_id == "2026123456789123_pressure"
    assert entity.entity_description is description
    assert entity._state is config_entry.runtime_data.state
    assert entity.device_info is config_entry.runtime_data.device_info
    assert entity.should_poll is False
    assert entity.has_entity_name is True
