"""Tests for LinknLink entities."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_entities(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test gateway and child-device entities."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.emotion_ultra_temperature").state == "23.5"
    assert hass.states.get("sensor.emotion_ultra_distance").state == "50"
    assert hass.states.get("sensor.radar_temperature").state == "24.0"
