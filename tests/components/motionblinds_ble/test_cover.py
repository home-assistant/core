"""Tests for Motionblinds BLE covers."""

from typing import Any
from unittest.mock import Mock

from motionblindsble.const import MotionBlindType, MotionRunningType
import pytest

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("motionblinds_ble_connect")
@pytest.mark.parametrize("blind_type", [MotionBlindType.VENETIAN])
@pytest.mark.parametrize(
    ("service", "method", "kwargs"),
    [
        (SERVICE_OPEN_COVER, "open", {}),
        (SERVICE_CLOSE_COVER, "close", {}),
        (SERVICE_OPEN_COVER_TILT, "open_tilt", {}),
        (SERVICE_CLOSE_COVER_TILT, "close_tilt", {}),
        (SERVICE_SET_COVER_POSITION, "position", {ATTR_POSITION: 5}),
        (SERVICE_SET_COVER_TILT_POSITION, "tilt", {ATTR_TILT_POSITION: 10}),
        (SERVICE_STOP_COVER, "stop", {}),
        (SERVICE_STOP_COVER_TILT, "stop", {}),
    ],
)
async def test_cover_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motion_device: Mock,
    name: str,
    service: str,
    method: str,
    kwargs: dict[str, Any],
) -> None:
    """Test cover service."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: f"cover.{name}", **kwargs},
        blocking=True,
    )
    getattr(mock_motion_device, method).assert_called_once()


@pytest.mark.usefixtures("motionblinds_ble_connect")
@pytest.mark.parametrize(
    ("running_type", "state"),
    [
        (None, "unknown"),
        (MotionRunningType.STILL, "unknown"),
        (MotionRunningType.OPENING, CoverState.OPENING),
        (MotionRunningType.CLOSING, CoverState.CLOSING),
    ],
)
async def test_cover_update_running(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motion_device: Mock,
    name: str,
    running_type: str | None,
    state: str,
) -> None:
    """Test updating running status."""

    await setup_integration(hass, mock_config_entry)

    async_update_running = mock_motion_device.register_running_callback.call_args[0][0]

    async_update_running(running_type)
    assert hass.states.get(f"cover.{name}").state == state


@pytest.mark.usefixtures("motionblinds_ble_connect")
@pytest.mark.parametrize(
    ("position", "tilt", "state"),
    [
        (None, None, "unknown"),
        (0, 0, CoverState.OPEN),
        (50, 90, CoverState.OPEN),
        (100, 180, CoverState.CLOSED),
    ],
)
async def test_cover_update_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motion_device: Mock,
    name: str,
    position: int,
    tilt: int,
    state: str,
) -> None:
    """Test updating cover position and tilt."""

    await setup_integration(hass, mock_config_entry)

    async_update_position = mock_motion_device.register_position_callback.call_args[0][
        0
    ]

    async_update_position(position, tilt)
    assert hass.states.get(f"cover.{name}").state == state
