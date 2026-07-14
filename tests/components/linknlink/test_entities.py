"""Tests for LinknLink entities."""

from unittest.mock import AsyncMock

from aiolinknlink import UltraConnectionError
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration
from .conftest import SESSION

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
    assert hass.states.get("binary_sensor.emotion_ultra_motion").state == "on"
    assert hass.states.get("sensor.radar_temperature").state == "24.0"
    assert hass.states.get("binary_sensor.radar_motion").state == "on"
    assert hass.states.get("switch.radar_power").state == "on"


async def test_switch_control(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test controlling a child-device switch."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.radar_power"},
        blocking=True,
    )

    mock_linknlink_client.control.assert_awaited_once_with(
        SESSION,
        "power",
        "radar-1",
        {"power": False},
    )
    assert mock_linknlink_client.refresh.await_count == 2


async def test_switch_control_error(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an error while controlling a child-device switch."""
    mock_linknlink_client.control.side_effect = UltraConnectionError("offline")
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError, match="Failed to control"):
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.radar_power"},
            blocking=True,
        )
