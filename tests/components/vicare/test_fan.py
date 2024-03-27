"""Test ViCare fan."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


async def test_fan(
    hass: HomeAssistant,
    mock_vicare_fan: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the ViCare fan."""
    assert hass.states.get("fan.model0_ventilation") == snapshot
