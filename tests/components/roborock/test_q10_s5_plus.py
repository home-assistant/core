"""Tests for Roborock Q10 S5+ fixtures."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from roborock.data.b01_q10.b01_q10_code_mappings import (
    B01_Q10_DP,
    YXDeviceState,
    YXFanLevel,
    YXWaterLevel,
)

from .mock_data import Q10_STATUS_DATA


@pytest.fixture
def q10_status_trait() -> AsyncMock:
    """Create a mock Q10 status trait."""
    trait = AsyncMock()
    trait.data = deepcopy(Q10_STATUS_DATA)

    async def refresh_side_effect():
        return trait.data

    trait.refresh = AsyncMock(side_effect=refresh_side_effect)
    return trait


async def test_q10_status_data_shape() -> None:
    """Validate Q10 status fixture data keys and values."""
    assert Q10_STATUS_DATA[B01_Q10_DP.STATUS] == YXDeviceState.STANDBY_STATE.code
    assert Q10_STATUS_DATA[B01_Q10_DP.BATTERY] == 100
    assert Q10_STATUS_DATA[B01_Q10_DP.FAN_LEVEL] == YXFanLevel.NORMAL.code
    assert Q10_STATUS_DATA[B01_Q10_DP.WATER_LEVEL] == YXWaterLevel.MIDDLE.code
    assert Q10_STATUS_DATA[B01_Q10_DP.MAIN_BRUSH_LIFE] == 5000
    assert Q10_STATUS_DATA[B01_Q10_DP.SIDE_BRUSH_LIFE] == 3000
    assert Q10_STATUS_DATA[B01_Q10_DP.FILTER_LIFE] == 1500
    assert Q10_STATUS_DATA[B01_Q10_DP.CLEAN_TIME] == 15


async def test_q10_status_trait_refresh(q10_status_trait: AsyncMock) -> None:
    """Ensure the mock status trait returns the fixture data on refresh."""
    refreshed = await q10_status_trait.refresh()
    assert refreshed == Q10_STATUS_DATA


async def test_q10_status_state_updates(q10_status_trait: AsyncMock) -> None:
    """Ensure status updates can be applied to the fixture data."""
    q10_status_trait.data[B01_Q10_DP.STATUS] = YXDeviceState.ROBOT_SWEEP_AND_MOPING.code
    assert (
        q10_status_trait.data[B01_Q10_DP.STATUS]
        == YXDeviceState.ROBOT_SWEEP_AND_MOPING.code
    )
