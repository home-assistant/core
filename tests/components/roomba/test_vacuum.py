"""Tests for the Roomba vacuum platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.vacuum import VacuumActivity, VacuumEntityFeature
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_ID = "vacuum.test_roomba"


@pytest.mark.parametrize(
    ("phase", "cycle", "expected"),
    [
        ("charge", "none", VacuumActivity.DOCKED),
        # Docked to recharge in the middle of a mission stays docked instead of
        # being reported as paused (regression test for #148287).
        ("charge", "clean", VacuumActivity.DOCKED),
        ("hmMidMsn", "clean", VacuumActivity.CLEANING),
        ("hmPostMsn", "clean", VacuumActivity.RETURNING),
        ("run", "clean", VacuumActivity.CLEANING),
        ("pause", "clean", VacuumActivity.PAUSED),
        # Stopped on the floor mid-mission is a paused state.
        ("stop", "clean", VacuumActivity.PAUSED),
        ("stop", "none", VacuumActivity.IDLE),
        ("stuck", "clean", VacuumActivity.ERROR),
    ],
)
async def test_vacuum_activity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
    phase: str,
    cycle: str,
    expected: VacuumActivity,
) -> None:
    """Test the vacuum activity mapping from the reported mission status."""
    mock_roomba.master_state["state"]["reported"]["cleanMissionStatus"] = {
        "cycle": cycle,
        "phase": phase,
    }

    with patch("homeassistant.components.roomba.PLATFORMS", [Platform.VACUUM]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("extra_state", "expect_fan_speed_support", "expected_fan_speed"),
    [
        # 67 is OVERLAP_STANDARD.
        ({"rankOverlap": 67}, True, "Standard-1"),
        # Combo models report a mop pad but no rankOverlap.
        ({}, False, None),
    ],
)
async def test_braava_fan_speed_requires_rank_overlap(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roomba: AsyncMock,
    extra_state: dict[str, Any],
    expect_fan_speed_support: bool,
    expected_fan_speed: str | None,
) -> None:
    """Test that fan speed is only offered when it can be produced."""
    reported = mock_roomba.master_state["state"]["reported"]
    reported["detectedPad"] = "reusableWet"
    # fan_speed reads the "disposable" key.
    reported["padWetness"] = {"disposable": 1, "reusable": 1}
    reported.pop("rankOverlap", None)
    reported.update(extra_state)

    with patch("homeassistant.components.roomba.PLATFORMS", [Platform.VACUUM]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    supported = VacuumEntityFeature(state.attributes["supported_features"])
    assert bool(supported & VacuumEntityFeature.FAN_SPEED) is expect_fan_speed_support
    assert state.attributes.get("fan_speed") == expected_fan_speed
