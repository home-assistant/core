"""Tests for LinknLink entities."""

from dataclasses import replace
from unittest.mock import AsyncMock

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import STATE

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


async def test_entities_unavailable_when_device_reports_offline(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entities are unavailable when the protocol reports offline."""
    mock_linknlink_client.refresh.return_value = replace(STATE, online=False)

    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("sensor.emotion_ultra_temperature").state == STATE_UNAVAILABLE
    )
