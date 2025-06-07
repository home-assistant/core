"""Tests for ActronAir entity classes."""

from unittest.mock import AsyncMock

from homeassistant.components.actronair.entity import (
    ActronAirWallController,
    ActronAirZoneDevice,
)


async def test_wall_controller_entity() -> None:
    """Test initialization of ActronAir Wall Controller entity."""
    mock_coordinator = AsyncMock()
    serial_number = "12345"

    entity = ActronAirWallController(mock_coordinator, serial_number)

    assert entity.name == "ActronAir Wall Controller"
    assert entity.unique_id == f"actronair_{serial_number}"
    assert entity.device_info["model"] == "NEO Controller"


async def test_zone_entity() -> None:
    """Test initialization of ActronAir Zone entity."""
    mock_coordinator = AsyncMock()
    wall_serial = "12345"
    zone_id = 1

    entity = ActronAirZoneDevice(mock_coordinator, wall_serial, zone_id)

    assert entity.name == "Zone 1"
    assert entity.unique_id == f"actronair_{wall_serial}_zone_{zone_id}"
    assert entity.device_info["model"] == "Zone Controller"
