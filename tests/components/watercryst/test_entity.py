"""Tests for WATERCryst entities."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.watercryst.entity import WatercrystEntity
from homeassistant.helpers.device_registry import DeviceInfo


def test_entity_initialization() -> None:
    """Test shared WATERCryst entity attributes."""
    device_info = DeviceInfo(identifiers={("watercryst", "1234567890")})
    client = MagicMock()
    runtime_data = SimpleNamespace(
        bsn="1234567890",
        device_info=device_info,
        client=client,
    )
    config_entry = MagicMock()
    config_entry.runtime_data = runtime_data
    description = SensorEntityDescription(key="pressure")

    entity = WatercrystEntity(config_entry, description)

    assert entity.device_info is device_info
    assert entity.unique_id == "1234567890_pressure"
    assert entity.entity_description is description
    assert entity.runtime_data is runtime_data
    assert entity._client is client
    assert entity.should_poll is False
    assert entity.has_entity_name is True
