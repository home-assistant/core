"""Tests for the Envisalink setup."""

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest

from homeassistant.components.envisalink.alarm_control_panel import (
    async_setup_platform as alarm_setup_platform,
)
from homeassistant.components.envisalink.binary_sensor import (
    async_setup_platform as binary_sensor_setup_platform,
)
from homeassistant.components.envisalink.sensor import (
    async_setup_platform as sensor_setup_platform,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from .conftest import ALARM_ENTITY, DOMAIN, KEYPAD_ENTITY, ZONE_ENTITY, setup_envisalink


async def test_setup_creates_entities(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test setup creates the alarm, keypad and zone entities."""
    assert await setup_envisalink(hass)

    assert hass.states.get(ALARM_ENTITY) is not None
    assert hass.states.get(KEYPAD_ENTITY) is not None
    assert hass.states.get(ZONE_ENTITY) is not None


async def test_setup_fails_on_login_failure(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test setup returns False when the Envisalink rejects the login."""
    mock_controller.start.side_effect = lambda: mock_controller.callback_login_failure(
        None
    )

    assert await setup_envisalink(hass) is False
    assert hass.states.get(ALARM_ENTITY) is None


async def test_setup_succeeds_on_connection_timeout(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test setup proceeds (retry mode) when the first connection times out."""
    mock_controller.start.side_effect = lambda: mock_controller.callback_login_timeout(
        None
    )

    assert await setup_envisalink(hass)
    assert hass.states.get(ALARM_ENTITY) is not None


async def test_controller_stopped_on_shutdown(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the controller connection is stopped on Home Assistant shutdown."""
    assert await setup_envisalink(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_controller.stop.assert_called_once()


@pytest.mark.parametrize(
    "setup_platform",
    [
        alarm_setup_platform,
        binary_sensor_setup_platform,
        sensor_setup_platform,
    ],
)
async def test_platform_setup_without_discovery_is_noop(
    hass: HomeAssistant, setup_platform: Callable
) -> None:
    """Test a platform set up directly (no discovery info) adds no entities."""
    add_entities = MagicMock()
    await setup_platform(hass, {}, add_entities, None)
    add_entities.assert_not_called()


async def test_invoke_custom_function_service(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the PGM service forwards the code, partition and function."""
    assert await setup_envisalink(hass)

    await hass.services.async_call(
        DOMAIN,
        "invoke_custom_function",
        {"pgm": "1", "partition": "1"},
        blocking=True,
    )

    mock_controller.command_output.assert_called_once_with("1234", "1", "1")
