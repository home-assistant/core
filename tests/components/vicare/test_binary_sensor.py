"""Test ViCare binary sensors."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    "entity_id",
    [
        "burner",
        "circulation_pump",
        "frost_protection",
    ],
)
async def test_binary_sensors(
    hass: HomeAssistant,
    mock_vicare_gas_boiler: MagicMock,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test the ViCare binary sensor."""
    assert hass.states.get(f"binary_sensor.model0_{entity_id}") == snapshot
