"""Tests for Motionblinds BLE covers."""

from typing import Any
from unittest.mock import patch

from motionblindsble.const import MotionBlindType, MotionRunningType
from motionblindsble.device import MotionDevice
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
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.components.motionblinds_ble.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from . import setup_platform


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
    hass: HomeAssistant, service: str, method: str, kwargs: dict[str, Any]
) -> None:
    """Test cover service."""

    _, name = await setup_platform(
        hass, [Platform.COVER], blind_type=MotionBlindType.VENETIAN
    )

    with patch(
        f"homeassistant.components.motionblinds_ble.MotionDevice.{method}"
    ) as func:
        await hass.services.async_call(
            COVER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: f"cover.{name}", **kwargs},
            blocking=True,
        )
        func.assert_called_once()

    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("running_type", "state"),
    [
        (None, "unknown"),
        (MotionRunningType.STILL, "unknown"),
        (MotionRunningType.OPENING, STATE_OPENING),
        (MotionRunningType.CLOSING, STATE_CLOSING),
    ],
)
async def test_cover_update_running(
    hass: HomeAssistant, running_type: str | None, state: str
) -> None:
    """Test updating running status."""

    config_entry, name = await setup_platform(
        hass, [Platform.COVER], blind_type=MotionBlindType.VENETIAN
    )

    device: MotionDevice = hass.data[DOMAIN][config_entry.entry_id]
    device.update_running(running_type)
    assert hass.states.get(f"cover.{name}").state == state


@pytest.mark.parametrize(
    ("position", "tilt", "state"),
    [
        (None, None, "unknown"),
        (0, 0, STATE_OPEN),
        (50, 90, STATE_OPEN),
        (100, 180, STATE_CLOSED),
    ],
)
async def test_cover_update_position(
    hass: HomeAssistant, position: int, tilt: int, state: str
) -> None:
    """Test updating cover position and tilt."""

    config_entry, name = await setup_platform(
        hass, [Platform.COVER], blind_type=MotionBlindType.VENETIAN
    )

    device: MotionDevice = hass.data[DOMAIN][config_entry.entry_id]
    device.update_position(position, tilt)
    assert hass.states.get(f"cover.{name}").state == state
