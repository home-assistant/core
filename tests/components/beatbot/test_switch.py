"""Tests for Beatbot switch entities."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.beatbot.iot.const import (
    INTERFACE_CHILD_LOCK,
    INTERFACE_VOICE_DISTURB,
)
from homeassistant.components.beatbot.models import BeatbotDeviceData
from homeassistant.components.beatbot.switch import SWITCH_DESCRIPTIONS, BeatbotSwitch

DEVICE_ID = "base-station-1"


def _make_coordinator() -> SimpleNamespace:
    """Build a coordinator containing both switch states."""
    device = BeatbotDeviceData(
        device_id=DEVICE_ID,
        product_id="base-x",
        product_category="clean_base_station",
        work_status=0,
        work_mode=0,
        error_code=0,
        battery_level=0,
        versions=[],
        is_online=True,
        child_lock=True,
        voice_disturb=False,
    )
    return SimpleNamespace(
        data={DEVICE_ID: device},
        last_update_success=True,
        api=SimpleNamespace(set_switch=AsyncMock()),
        async_schedule_device_state_refresh=MagicMock(),
    )


@pytest.mark.parametrize(
    ("description_index", "expected_state"),
    [(0, True), (1, False)],
)
def test_switch_reflects_device_state(
    description_index: int, expected_state: bool
) -> None:
    """Reflect the matching device field in each switch."""
    entity = BeatbotSwitch(
        _make_coordinator(), DEVICE_ID, SWITCH_DESCRIPTIONS[description_index]
    )

    assert entity.is_on is expected_state


@pytest.mark.parametrize(
    ("description_index", "turn_on", "interface_info", "expected_label"),
    [
        (0, True, INTERFACE_CHILD_LOCK, "on"),
        (1, False, INTERFACE_VOICE_DISTURB, "off"),
    ],
)
async def test_switch_sends_on_off_label(
    description_index: int,
    turn_on: bool,
    interface_info: str,
    expected_label: str,
) -> None:
    """Send the backend label for switch commands."""
    coordinator = _make_coordinator()
    entity = BeatbotSwitch(
        coordinator, DEVICE_ID, SWITCH_DESCRIPTIONS[description_index]
    )

    if turn_on:
        await entity.async_turn_on()
    else:
        await entity.async_turn_off()

    coordinator.api.set_switch.assert_awaited_once_with(
        DEVICE_ID, interface_info, expected_label
    )
    coordinator.async_schedule_device_state_refresh.assert_called_once_with(DEVICE_ID)
