"""Test ViCare binary sensors."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    "entity_id",
    [
        "room_temperature"
        "room_humidity",
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    mock_vicare_room_sensors: MagicMock,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test the ViCare binary sensor."""
    # assert hass.states.get(f"binary_sensor.model0_{entity_id}") == snapshot
